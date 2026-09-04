# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Snakestream is a Java-8-streams-style API for Python, built entirely around `async`/`await`. Every stream, regardless of what kind of source it's built from (list, generator, async generator, iterator, async iterator, or a bare object), is normalized internally into an `AsyncGenerator` and consumed lazily.

## Commands

This project uses `uv`.

```bash
uv sync                                    # install deps (incl. dev group)
uv run pytest                              # run full test suite (coverage runs by default, see pyproject.toml addopts)
uv run pytest tests/test_map.py            # run a single test file
uv run pytest tests/test_map.py::test_name -k "..."  # run a single test
uv run pytest --cov-fail-under=98          # enforce coverage threshold (as CI does on the newest interpreter)
uv run ruff check .                        # lint
uv run ruff format --check .               # verify formatting
uv run ruff format .                       # apply formatting
uv run ty check src                        # static type check
uv run --with pip-audit pip-audit          # dependency vulnerability audit
uv run --python 3.14t pytest               # run the suite on the free-threaded build (installs 3.14t via uv if not already present)
```

CI (`.github/workflows/check.yml`) runs `code_check` on two Python 3.14 legs — GIL-enabled (`3.14`) and free-threaded (`3.14t`, PEP 779). The ruff checks and `uv run pytest` run on both legs; `ty`, `pip-audit` and the coverage gate run on the GIL-enabled leg only, since none of the three varies by interpreter build. `install_smoke_test` stays at the single `3.14` leg — the package is pure Python with no dependencies, so a free-threaded leg there would install a byte-identical artifact. Match that when validating changes.

## Naming

A module-level name in `src/snakestream` carries a leading underscore **iff** no other module in `src/snakestream` uses it. A name another module imports is bare; a name used only where it is defined is underscored. The underscore is not a public-API marker — the package's public surface is the module path a caller imports from (`snakestream.collectors.to_list`, `snakestream.comparator.comparing`, ...) plus the two names `snakestream/__init__.py` re-exports (`Stream`, and as of this rule, nothing else). Every module below `__init__.py` is already an implementation detail, so a bare name inside one is not a promise that callers may import it.

`tests/` may import anything, including an underscore-prefixed name — that is white-box testing, not a violation, and does not make the name non-local. `tests/test_name_visibility.py` enforces the decidable half of the rule (a build check: no module under `src/snakestream` may import a private name from another module in the package); the other half — that a bare name used only inside its module really is absent from every caller — is a one-time judgment applied by hand, since there is no maintained list of caller-facing names to check it against.

Class members are unaffected: a method or attribute's leading underscore still means "not for callers," regardless of which modules use the class.

## Architecture

### The chain-of-ops model

`Stream` (`stream.py`) holds four things that matter: `self._stream`, the normalized `AsyncGenerator` source; `self._chain`, a list of unapplied `Op` objects; `self._executor`, the value that decides *how* the pipeline runs; and `self._consumed`, which invalidates a reference once it has been extended.

Calling an intermediate operation like `.map()` or `.filter()` does **not** execute anything — it appends an `Op` to the chain and returns a **new** stream via `_derive()`, marking the receiver consumed (see the `pipeline-immutability` spec; reusing an extended reference raises `IllegalStateException`). An `Op` carries the arguments the user passed and builds the `Sink` that does the per-element work, once per sink chain it is linked into.

Nothing runs until a terminal operation drives the chain. Two module-level helpers in `execution.py`, both named after their Java counterparts, do the actual work: `_wrap_sink(chain, terminal)` links the ops onto a terminal sink innermost-last and returns the head (Java's `AbstractPipeline.wrapSink()`), and `_copy_into(head, src, state_map)` pushes every source element into that head, honouring cancellation (Java's `copyInto()`).

This means:
- Intermediate ops (`filter`, `map`, `flat_map`, `sorted`, `distinct`, `peek`, `limit`, `skip`) live in `stream.py`, only ever queue an `Op`, and always return a new instance.
- Terminal ops (`collect`, `reduce`, `for_each`, `find_any`, `max`/`min`, `all_match`/`any_match`/`none_match`, `count`) are `async def` methods that call `self._evaluate(terminal_sink)` to push values through the chain.
- Both sync and async user-supplied callables are accepted everywhere. Awaitability is classified once per callable per composition rather than per element — see `callable_dispatch.py` and the `callable-dispatch` spec.

### Sequential vs. parallel execution

Execution mode is a **value, not a type**. There is no `ParallelStream` class. `execution.py` holds two executors and the primitives they are built from:

```
_stream_through(chain, src)             -> AsyncGenerator   one worker, elements out lazily
_feed_through(chain, src, terminal)     -> value            fused push, nothing buffered
_drain(elements, terminal)              -> value            any generator into a terminal
_fork_join_through(chain, src, workers, demand, ordered_in)
                                       -> AsyncGenerator   contiguous batches, each on its own thread

SEQUENTIAL.elements = _stream_through      SEQUENTIAL.value = _feed_through  (override)
FORK_JOIN.elements  = _fork_join_through   FORK_JOIN.value  = inherited generic
```

`Executor.value()`'s generic default is `_drain(self.elements(...), terminal)`, which `_ForkJoin` uses unchanged — each batch builds and tears down its own sink chain on its own OS thread, so there is no single, long-lived chain a terminal could be fused onto (fusing would need the terminal to accumulate correctly across concurrently-running batches, which is exactly the `Collector` combiner this library does not yet drive). `_Sequential.value()` overrides it with the fused push purely on measurement: composing and then draining costs +125% per element on `count()`. That override is the one asymmetry in the protocol; its docstring carries the figures.

`.parallel()` decomposes the source with `spliterator()` (`Spliterator[T]`, `stream.py`/`spliterator.py`) rather than racing `asyncio` tasks over a shared generator on one thread. `_fork_join_through()` pulls up to `WORKERS` contiguous batches at a time — `_pull_round()`, the one place a round touches the shared source, so there is no cross-coroutine contention on it to guard against — and dispatches each batch's chain onto its own OS thread via `asyncio.to_thread(_run_batch_sync, ...)`. Contiguous batches never scramble encounter order the way the old racing branches did, so there is no merge to restore it at: batch order already *is* encounter order, since batches are pulled in sequence. `WORKERS` (renamed from `PROCESSES`, since it now names threads rather than a process-pool design that was never built) defaults to 4; a batch's own elements still race each other concurrently within the batch (`_run_batch_async()`, one `_run_element()` task per item on the worker's own event loop), which is where the I/O concurrency the old racing executor bought is preserved rather than lost.

Whether "on its own OS thread" means real CPU parallelism depends on the interpreter build: GIL-bound on the standard build (only one thread runs Python bytecode at a time, confirmed at ~1.0x), genuinely parallel on the free-threaded build (3.14t, PEP 779; ~2x measured, but only once the source spans enough batches to spread across workers — a small source can land entirely in one worker's batch and see no benefit). Cheap, non-blocking callables pay a new cost on either build — a real `asyncio.to_thread` dispatch per batch rather than one more cooperatively-scheduled `asyncio` task — which scales with the number of batch dispatches (roughly `source size / BATCH_SIZE` at steady state), not with worker count alone, which is why `.sequential()` remains the documented remedy for a pipeline where `.parallel()` was never buying anything (see README's Migration entry, design.md's Risks, and `benchmark-findings.md`, all in `fork-join-executor-and-spliterator`).

A stream consults its executor in exactly two places: `iterator()` (`self._executor.elements(...)`) and `_evaluate()` (`self._executor.value(...)`). Both operations carry the consumer's `OrderDemand` declaration alongside the chain and the source — a second axis, orthogonal to which executor the stream carries, and the input to the delivery barrier described below. No terminal names an executor for itself any more. A terminal that needs encounter order says so as a *demand* — `OrderDemand`, the value it passes alongside the chain — and the executor it runs under is always the stream's. `find_first()` is the one terminal whose demand is unconditional (`ALWAYS`), which is why it has one implementation rather than a per-mode pair; `for_each_ordered()`'s is conditional (`IF_ORDERED`) like every other order-observing terminal's. Both used to name `SEQUENTIAL` and both stopped, because naming it forfeited the caller's mode to express an ordering demand, and went a step further than Java: `ForEachOrderedTask` is itself a fork-join task, and `FindTask` scans leftmost *across* branches rather than dropping to a sequential traversal.

`Stream._is_ordered()`, the private wrapper around `ordering.py`'s `is_ordered()` fold, has one caller left: `Stream.concat()`, which uses it to decide whether the concatenation inherits `unordered()`. It is deliberately not public: Java exposes only `isParallel()` and keeps `ORDERED` in the package-private `StreamOpFlag`.

`.parallel()` / `.sequential()` each derive with no op and their target executor — `_derive()` with its `op` argument omitted and `executor` set to `FORK_JOIN`/`SEQUENTIAL` — giving a new stream over the **same source and same chain**, differing only in its executor, with the receiver consumed. `sequential()`'s docstring carries the rules both obey and `parallel()` points at it. They deliberately do **not** compose — that is what makes them position-independent, matching Java, where `parallel()` sets a flag on the source stage. The last mode switch before a terminal governs the whole pipeline.

### The ordering barrier

Fork/join's batches are contiguous and pulled in sequence, so — unlike the old
racing executor's `FIRST_COMPLETED` merge — there is nothing that scrambles
encounter order to begin with. What still needs a barrier is an op whose
answer depends on an element's *position* (`sorted`, `limit`, `skip`,
`distinct`): it needs to see the whole stream, not one batch's worth, so the
chain still has to split around it. The whole encounter-order model — `Ordering`,
`OrderDemand`, `is_ordered()` and `split_point()` — lives in one file,
`ordering.py`; `sink.py` and `execution.py` each import from it what they need,
and `split_point()` itself is unchanged from the racing executor (design.md,
`fork-join-executor-and-spliterator`, decision 3) — only what runs at the split
is different.

`ordering.py`'s `split_point(chain, demand, ordered_in)` returns where order
has to be restored. Three clauses, first hit wins, and the third is the first
two again one level up — `Ordering.SET` is to `OrderDemand.ALWAYS` what
`order_sensitive` is to `OrderDemand.IF_ORDERED`:

- an op declaring `Ordering.SET` (`sorted()`, wherever it sits — a sort claims
  its output is ordered, so it must see the whole stream), or
- an op declaring `order_sensitive` **and** sitting at a position
  `is_ordered()` reports ordered (`limit`/`skip`/`distinct`) — an operation
  whose answer depends on an element's *position*, and
- `len(chain)`, when the **terminal** demands it — unconditionally
  (`ALWAYS`, `find_first()` alone), or conditionally (`IF_ORDERED`) with the
  pipeline ordered at the end of the chain. A split at the end means every op
  still runs concurrently and only delivery is reordered, which is Java's shape
  and costs no per-element concurrency.

When there is no split — every pipeline the caller declared `unordered()`
before the relevant point, and every order-blind terminal — `_fork_join_through()`
dispatches through `_fork_join_batches(..., ordered=False)`, which drops to
`_fork_join_unordered_batches()`: a sliding window of up to `WORKERS` batches
in flight, each refilled the moment an earlier one completes and yielded as
soon as *any* batch returns, rather than held for its round. This is what an
order-blind, short-circuiting terminal (`any_match()`, `find_any()`) needs and
the ordered form cannot give it — waiting out a whole round means waiting on
every batch's slowest element, including ones the terminal was never going to
look at.

When there is one, the chain splits there. The head runs through
`_fork_join_batches(head, source, workers, ordered=True)`, which dispatches
`_fork_join_ordered_batches()`: one round of up to `WORKERS` contiguous
batches at a time — `_pull_round()`, then `_run_round()` (each batch's chain
on its own thread via `asyncio.to_thread`) — yielded in batch order once the
whole round has returned. Batch order is encounter order for free, so there is
no merge to get wrong and nothing to reorder afterwards, unlike the old
racing executor's per-element index tag and release buffer. The barrier op
then runs a single ordinary pass (`_stream_through`) over that
already-ordered, concatenated batch output, and **everything after it resumes
fork/join afresh** — `_fork_join_through()` re-entering itself with
`ordered_in` carrying the ordering characteristic across the split, the same
seed `is_ordered()` and `split_point()` need for a resumed suffix. So
`.limit(n).map(fetch)` still runs `map` across batches, and an
order-observing terminal downstream of it gets its own delivery barrier from
the resumed dispatch.

Which terminals observe order is declared at each terminal's own call site, as
a bool passed to `_evaluate()` and on through `Executor.value()`/`elements()`.
`count()`, `for_each()`, `find_any()`, `max`/`min` and the `*_match` family
declare `NONE` and pay nothing (in the general case — see below for the one
bounded exception); `reduce()`, `to_array()`, the three-argument
`collect()`, `for_each_ordered()` and `iterator()` declare `IF_ORDERED`;
`collect(collector)` reads the collector's `Characteristics.UNORDERED` to pick
between those two. `find_first()` declares `ALWAYS`, alone: its demand survives
`unordered()`, which is coherent because contiguous batches always let order be
restored — `unordered()` clears the requirement to honour it, never the ability.

Read-ahead has no bespoke bound any more — no `_Window`, no per-branch slot
count. The steady-state in-flight amount is `WORKERS * BATCH_SIZE` (the same
`BATCH_SIZE` `Spliterator.try_split()` uses — one number for both, deliberately,
per design.md decision 1 — 4096 at the defaults, against the old window's 16),
with the first round smaller (`_FIRST_BATCH_SIZE`, 4 per worker) so a
short-circuiting terminal doesn't over-pull on its very first round. Every
reason the old window existed — memory held resident, latency behind a
straggler, wasted upstream invocations under a short-circuiting terminal —
still applies at this size, and the lever a caller is given for all three
remains `unordered()`, not a number. One bounded exception is new and
accepted rather than fixed: an order-blind, short-circuiting terminal may
still be delayed by a slow, unrelated element sharing its own batch with the
one that would have satisfied it, bounded by that batch's size — never by an
earlier one, and never unboundedly (design.md decision 10; see
`racing-encounter-order`'s "Read-ahead under an ordered racing pipeline is
bounded" requirement for the accepted-and-bounded framing this extends).

The split is internal. It is not a third executor, is not selectable, and
`is_parallel()` still reports the executor the stream carries.

### Collectors

`collect(collector)` (a terminal op) takes a `Collector` — Java's
`Collector<T,A,R>`: a `supplier`/`accumulator`/`combiner`/`finisher` quadruple,
each part sync or async, plus a `characteristics` frozenset (data, not a
callable, so it is neither invoked nor awaited) mirroring Java's
`Collector.Characteristics` — and drives the composed chain into a
`CollectorSink` built from it. `Characteristics` ships one member,
`UNORDERED`, declared by `to_set()` and derived by `mapping()`/
`collecting_and_then()` from their downstream. `collect()` reads it to decide
whether the racing executor owes the collector a reorder barrier. The two halves
live in two modules, on Java's own naming:
`collector.py` holds the *protocol* (`Collector`, `CollectorSink`,
`StreamingCollector`, `to_generator`), and `collectors.py` holds the ~20
*factories* (`to_list()`, `to_set()`, `counting()`, `grouping_by()`, ...).
The import edge runs one way, `collectors` -> `collector`, never back. Every
collector in `collectors.py` is a **factory** returning a `Collector`; there
are no bare instances. The one exception is `to_generator`, a
`StreamingCollector` wrapping a `(composition) -> AsyncGenerator` callable,
which is why it sits in `collector.py` beside the type rather than with the
factories: it is composed through the generator bridge instead of driven into
a sink, and `collect(to_generator)` returns an `AsyncGenerator` directly
rather than something to await. Passing anything else raises
`StreamBuildException`.

### Type aliases

`type.py` defines the functional-interface-style aliases (`Predicate`, `Mapper`, `FlatMapper`, `Comparator`, `Consumer`, `Accumulator`, `CloseHandler`) used throughout for typing user-supplied callables — each permits either a sync or async (`Awaitable`) implementation.

### AutoClose

`on_close()`/`close()` on `Stream` implement Java's AutoClose equivalent. `Stream` is itself a context manager, so `with stream as s:` is the idiom; `contextlib.closing()` still works and is what older examples use. Close handlers are plain no-arg callables, not stream-aware — useful when subclassing `Stream` to wrap an I/O-like resource.

Two guarantees that subclass relies on, both from `_derive()` copying the next stage rather than constructing it. A subclass's `__init__` runs **once per pipeline**, at the caller's own construction, not once per stage — so a resource acquired there is acquired once, and every stage shares it by identity, which is what makes the already-shared `_close_handlers` list coherent: registered once, released once by a single `close()`. And a subclass may define **any** `__init__` signature; nothing requires it to accept `(source, close_handlers)`, so `DsnStream(dsn)` acquiring a connection and calling `super().__init__(conn.rows())` is a supported shape. Both were false before `derive-without-reinit`, which is what made this use case close to unwritable.

### Python's data model

`Stream` satisfies the Python protocols whose Java counterparts it already claims — `__aiter__` for `BaseStream.iterator()`, `__enter__`/`__exit__` for `AutoCloseable`, `__repr__` for `toString()` — plus `__add__` as sugar over `Stream.concat`, the one member with no Java counterpart and a deliberate expansion of the 1:1 surface rather than a parity fix.

Being async-first decides the rest: `__len__`, `__iter__`, `__contains__`, `__getitem__`, `__reversed__` and `__eq__` demand a value synchronously and every terminal here is a coroutine, so they are refused rather than implemented. `__bool__` is the exception that proves it — it **raises**, because `object.__bool__` otherwise makes every stream truthy including an empty one, so `if stream:` answers wrong silently. `__getitem__` carries a trap worth remembering: Python synthesizes an iterator from it when `__iter__` is absent, so adding slice support would make `for x in stream` loop forever over `stream[0]`, `stream[1]`, …; anyone adding it must add `__iter__` raising in the same change. See the `python-data-model` spec, which records the refusals as decisions.

An op renders its own name for `__repr__` (`Op.__repr__` in `sink.py`, derived from the class name: `FlatMapOp` -> `flat_map`), so `Stream.__repr__` only formats a list.

## Feature-parity tracking

README.md tracks Java Stream API parity in detail (implemented / not-yet-implemented / intentionally-skipped methods, and a migration log of breaking renames pre-1.0). Check it before assuming a Java Stream method is or isn't implemented, and update it when adding or renaming public API surface.
