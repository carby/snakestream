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
```

CI (`.github/workflows/check.yml`) runs the ruff checks, `uv run pytest`, `ty`, `pip-audit` and the coverage gate across Python 3.10–3.14; `ty`, `pip-audit`, and the coverage gate only run on the 3.14 leg. Match that when validating changes.

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
stream_through(chain, src)          -> AsyncGenerator   one worker, elements out lazily
group_through(chain, src, state)    -> AsyncGenerator   one worker, (index, outputs) per source element
race_through(chain, src, workers, ordered)
                                    -> AsyncGenerator   N branches racing one shared source
feed_through(chain, src, terminal)  -> value            fused push, nothing buffered
drain(elements, terminal)           -> value            any generator into a terminal

SEQUENTIAL.elements = stream_through      SEQUENTIAL.value = feed_through  (override)
RACING.elements     = race_through        RACING.value     = inherited generic
```

`Executor.value()`'s generic default is `drain(self.elements(...), terminal)`, which `Racing` uses unchanged — each racing branch owns its own sink chain, so there is no single chain to fuse a terminal onto. `Sequential.value()` overrides it with the fused push purely on measurement: composing and then draining costs +125% per element on `count()`. That override is the one asymmetry in the protocol; its docstring carries the figures.

A stream consults its executor in exactly two places: `iterator()` (`self._executor.elements(...)`) and `_evaluate()` (`self._executor.value(...)`). Both operations carry the consumer's `OrderDemand` declaration alongside the chain and the source — a second axis, orthogonal to which executor the stream carries, and the input to the delivery barrier described below. No terminal names an executor for itself any more. A terminal that needs encounter order says so as a *demand* — `OrderDemand`, the value it passes alongside the chain — and the executor it runs under is always the stream's. `find_first()` is the one terminal whose demand is unconditional (`ALWAYS`), which is why it has one implementation rather than a per-mode pair; `for_each_ordered()`'s is conditional (`IF_ORDERED`) like every other order-observing terminal's. Both used to name `SEQUENTIAL` and both stopped, because naming it forfeited the caller's mode to express an ordering demand, and went a step further than Java: `ForEachOrderedTask` is itself a fork-join task, and `FindTask` scans leftmost *across* branches rather than dropping to a sequential traversal.

`Stream._is_ordered()`, the private wrapper around `ordering.py`'s `is_ordered()` fold, has one caller left: `Stream.concat()`, which uses it to decide whether the concatenation inherits `unordered()`. It is deliberately not public: Java exposes only `isParallel()` and keeps `ORDERED` in the package-private `StreamOpFlag`.

`.parallel()` / `.sequential()` each derive with no op and their target executor — `_derive()` with its `op` argument omitted and `executor` set to `RACING`/`SEQUENTIAL` — giving a new stream over the **same source and same chain**, differing only in its executor, with the receiver consumed. `sequential()`'s docstring carries the rules both obey and `parallel()` points at it. They deliberately do **not** compose — that is what makes them position-independent, matching Java, where `parallel()` sets a flag on the source stage. The last mode switch before a terminal governs the whole pipeline.

### The ordering barrier

Racing destroys encounter order at the `FIRST_COMPLETED` merge. Two things want
it back, and one mechanism gives it to both: `race_through()` has a second gear,
and whether it engages is a property of the chain plus the consumer, not of the
executor. The whole encounter-order model behind this section — `Ordering`,
`OrderDemand`, `is_ordered()` and `_split_point()` — lives in one file,
`ordering.py`; `sink.py` and `execution.py` each import from it what they need.

`ordering.py`'s `_split_point(chain, demand, ordered_in)` returns where order
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
  still races and only delivery is reordered, which is Java's shape and costs no
  per-element concurrency.

When there is no split — every pipeline the caller declared `unordered()` before
the relevant point, and every order-blind terminal — `race_through()` runs
exactly the code it always did, at the same per-element cost.

When there is one, the chain splits there. The head races across branches as
ever, but over `_guarded(shared, lock, window)`, which tags each element with
the source index it assigns under the lock — the last point at which pull order
still *is* encounter order. Each branch runs `group_through()` rather than
`stream_through()`, yielding `(index, outputs)`: everything the head emitted for
one source element, since a head chain does not preserve one output per input
(`filter` drops, `flat_map` multiplies) and the group is the invariant a
per-element tag is not. `_release_in_order()` holds arriving groups until every
earlier index has gone out, and `_run_ordered_tail()` takes the rest: the
barrier op alone runs in one ordered pass, and **everything after it races**,
re-entering `race_through()` with `ordered_in` carrying the ordering
characteristic across the split. So `.limit(n).map(fetch)` races the `map`, and
an order-observing terminal downstream of it gets its own delivery barrier from
the resumed race. `is_ordered(chain, upto, initial)`'s `initial` seed exists for
exactly that re-entry: a suffix's ordering was decided by ops no longer in the
list.

Which terminals observe order is declared at each terminal's own call site, as
a bool passed to `_evaluate()` and on through `Executor.value()`/`elements()`.
`count()`, `for_each()`, `find_any()`, `max`/`min` and the `*_match` family
declare `NONE` and pay nothing; `reduce()`, `to_array()`, the three-argument
`collect()`, `for_each_ordered()` and `iterator()` declare `IF_ORDERED`;
`collect(collector)` reads the collector's `Characteristics.UNORDERED` to pick
between those two. `find_first()` declares `ALWAYS`, alone: its demand survives
`unordered()`, which is coherent because the barrier can always restore
encounter order — `_guarded()` assigns the source index under the lock, and
`unordered()` clears the requirement to honour it, never the ability.

Read-ahead is bounded by `_in_flight(workers)` — `_IN_FLIGHT_PER_WORKER` slots
per branch, 16 at the default worker count — fixed on the `_Window` at
construction and enforced in `_guarded()` where the index is assigned, the only
place a pull happens, so the bound costs no new synchronisation point. It scales
with the branch count rather than being a bare number because the tuning curve
knees at one slot per worker, so the ratio is what governs. The value is
deliberately private and spec'd that way: it bounds three things at once —
buffer memory, latency behind a straggler, and how many elements a chain
callable runs on under a short-circuiting terminal — and the lever a caller is
given for all three is `unordered()`, not a number. A branch waits *outside* the
lock and re-checks after acquiring it; waiting while holding it would stall the
very branch the merge is waiting for. Head-of-line blocking remains, as it
must; `unordered()` is the escape hatch, and is what makes it a real
performance lever rather than a semantic footnote.

The split is internal. It is not a third executor, is not selectable, and
`is_parallel()` still reports the executor the stream carries.

### Collectors

`collect(collector)` (a terminal op) takes a `Collector` — Java's
`Collector<T,A,R>`: a `supplier`/`accumulator`/`combiner`/`finisher` quadruple,
each part sync or async, plus a `characteristics` frozenset (data, not a
callable, so it is neither invoked nor awaited) mirroring Java's
`Collector.Characteristics` — and drives the composed chain into a
`_CollectorSink` built from it. `Characteristics` ships one member,
`UNORDERED`, declared by `to_set()` and derived by `mapping()`/
`collecting_and_then()` from their downstream. `collect()` reads it to decide
whether the racing executor owes the collector a reorder barrier. The two halves
live in two modules, on Java's own naming:
`collector.py` holds the *protocol* (`Collector`, `_CollectorSink`,
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

An op renders its own name for `__repr__` (`Op.__repr__` in `sink.py`, derived from the class name: `_FlatMapOp` -> `flat_map`), so `Stream.__repr__` only formats a list.

## Feature-parity tracking

README.md tracks Java Stream API parity in detail (implemented / not-yet-implemented / intentionally-skipped methods, and a migration log of breaking renames pre-1.0). Check it before assuming a Java Stream method is or isn't implemented, and update it when adding or renaming public API surface.
