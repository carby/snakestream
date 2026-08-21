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

### The chain-of-closures model

`BaseStream` (`base_stream.py`) holds two things: `self._stream`, the normalized `AsyncGenerator` source, and `self._chain`, a list of unapplied intermediate-operation closures. Calling an intermediate operation like `.map()` or `.filter()` on `Stream` does **not** execute anything — it appends an `async def fn(iterable) -> AsyncGenerator` closure to `self._chain` and returns `self` (mutation, not a new object). Nothing runs until a terminal operation calls `self._compose()`, which recursively feeds each closure the previous one's output (`_sequential`), building a single lazily-evaluated async generator pipeline from source through every queued step.

This means:
- Intermediate ops (`filter`, `map`, `flat_map`, `sorted`, `distinct`, `peek`, `limit`) live in `stream.py` and only ever queue closures.
- Terminal ops (`collect`, `reduce`, `for_each`, `find_any`, `max`/`min`, `all_match`/`any_match`/`none_match`, `count`) are `async def` methods that drive `self._compose()` to actually pull values through the chain.
- Both sync and async user-supplied callables (predicates, mappers, comparators, consumers) are accepted everywhere; each operation checks `iscoroutinefunction(...)` and awaits or calls accordingly.

### Sequential vs. parallel execution

`ParallelStream` (`parallel_stream.py`) subclasses `Stream` and overrides `_compose()` to fan the *same* chain of closures out across `PROCESSES` (default 4) independent async iterators pulling from the same underlying source, racing their `__anext__()` calls with `asyncio.wait(..., FIRST_COMPLETED)` and re-issuing a new `__anext__()` task per iterator as results land. This means parallel mode does not preserve ordering. `.sequential()` / `.parallel()` on `BaseStream` compose the current chain into a fresh generator and hand it to a new `Stream`/`ParallelStream`, resetting the chain — so switching modes mid-pipeline is supported and cheap.

### Collectors

`collect(collector)` (a terminal op) takes a `Collector` — Java's
`Collector<T,A,R>`: a `supplier`/`accumulator`/`combiner`/`finisher` quadruple,
each part sync or async — and drives the composed chain into a `_CollectorSink`
built from it. Every collector in `collector.py` (`to_list()`, `to_set()`,
`counting()`, `grouping_by()`, ...) is a **factory** returning a `Collector`;
there are no bare instances. The one exception is `to_generator`, a
`StreamingCollector` wrapping a `(composition) -> AsyncGenerator` callable: it
is composed through the generator bridge instead of driven into a sink, and
`collect(to_generator)` returns an `AsyncGenerator` directly rather than
something to await. Passing anything else raises `StreamBuildException`.

### Type aliases

`type.py` defines the functional-interface-style aliases (`Predicate`, `Mapper`, `FlatMapper`, `Comparator`, `Consumer`, `Accumulator`, `CloseHandler`) used throughout for typing user-supplied callables — each permits either a sync or async (`Awaitable`) implementation.

### AutoClose

`on_close()`/`close()` on `BaseStream` implement Java's AutoClose equivalent, meant to be paired with `contextlib.closing()`. Close handlers are plain no-arg callables, not stream-aware — useful when subclassing `Stream` to wrap an I/O-like resource.

## Feature-parity tracking

README.md tracks Java Stream API parity in detail (implemented / not-yet-implemented / intentionally-skipped methods, and a migration log of breaking renames pre-1.0). Check it before assuming a Java Stream method is or isn't implemented, and update it when adding or renaming public API surface.
