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
race_through(chain, src, workers)   -> AsyncGenerator   N branches racing one shared source
feed_through(chain, src, terminal)  -> value            fused push, nothing buffered
drain(elements, terminal)           -> value            any generator into a terminal

SEQUENTIAL.elements = stream_through      SEQUENTIAL.value = feed_through  (override)
RACING.elements     = race_through        RACING.value     = inherited generic
```

`Executor.value()`'s generic default is `drain(self.elements(...), terminal)`, which `Racing` uses unchanged — each racing branch owns its own sink chain, so there is no single chain to fuse a terminal onto. `Sequential.value()` overrides it with the fused push purely on measurement: composing and then draining costs +125% per element on `count()`. That override is the one asymmetry in the protocol; its docstring carries the figures.

A stream consults its executor in exactly two places: `_compose()` (`self._executor.elements(...)`) and `_evaluate()` (`self._executor.value(...)`). A terminal that needs encounter order regardless of the stream's mode names `SEQUENTIAL` explicitly at its own call site — `for_each_ordered()` always, `find_first()` when `is_ordered()`. That is why `find_first` has one implementation rather than a per-mode pair.

`.parallel()` / `.sequential()` go through `_derive_executor()`: a new stream over the **same source and same chain**, differing only in its executor, with the receiver consumed. They deliberately do **not** compose — that is what makes them position-independent, matching Java, where `parallel()` sets a flag on the source stage. The last mode switch before a terminal governs the whole pipeline. Racing does not preserve ordering.

### Collectors

`collect(collector)` (a terminal op) takes a `Collector` — Java's
`Collector<T,A,R>`: a `supplier`/`accumulator`/`combiner`/`finisher` quadruple,
each part sync or async — and drives the composed chain into a `_CollectorSink`
built from it. The two halves live in two modules, on Java's own naming:
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

`on_close()`/`close()` on `Stream` implement Java's AutoClose equivalent, meant to be paired with `contextlib.closing()`. Close handlers are plain no-arg callables, not stream-aware — useful when subclassing `Stream` to wrap an I/O-like resource.

## Feature-parity tracking

README.md tracks Java Stream API parity in detail (implemented / not-yet-implemented / intentionally-skipped methods, and a migration log of breaking renames pre-1.0). Check it before assuming a Java Stream method is or isn't implemented, and update it when adding or renaming public API surface.
