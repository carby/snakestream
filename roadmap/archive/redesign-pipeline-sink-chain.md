+++
id = "redesign-pipeline-sink-chain"
title = "Redesigned pipeline execution around a push-based `Sink` protocol"
filed = 2026-08-18
closed = 2026-08-18
outcome = "shipped"
+++

Redesigned pipeline execution from nested async-generator delegation to a
push-based `Sink` protocol (`begin(state_map)`/`accept(element)`/`end()`/
`cancellation_requested()`), replacing the closures-in-`_chain` model. New
`src/snakestream/sink.py` defines the protocol plus `IntermediateSink` (a
`downstream`-holding base that propagates `begin()`/`end()` and forwards
`cancellation_requested()`) and `TerminalSink` (creates its container in
`begin()`, accumulates in `accept()`, exposes the finished value via
`result()`) — the terminal seat a future `Collector` redesign can plug
into directly. `GeneratorBridgeSink` occupies that seat to let
`BaseStream._compose()` keep returning a plain `AsyncGenerator`: pushing
stays entirely internal to the chain, with a buffer-and-drain driving loop
(`BaseStream._drive()`) converting pushes back into yields, so all 11
terminal ops, every collector, `iterator()`, and `_concat` needed no
changes. All eight intermediate ops (`filter`, `map`, `flat_map`, `sorted`,
`peek`, `distinct`, `limit`, `skip`) are now op/sink pairs in `stream.py`
(`_FilterOp`/`_FilterSink`, etc.) — the op is a stateless, reusable
descriptor exposing `link(downstream) -> Sink` (and, for stateful ops, a
`make_shared_state()` factory), while the sink is built fresh per
composition and holds the actual per-composition state.
`make_state()`/`state_map` `getattr`-introspection is gone:
`ParallelStream._parallel()` now calls each op's `make_shared_state()`
directly to build one shared state map, passed into every racing branch's
`begin()`. `limit()`'s short-circuit moved from the op reaching up to
`aclose()` its own upstream to `cancellation_requested()` propagating to
the driving loop, which now owns closing the source (via a
`_maybe_aclosing()` helper tolerant of sources with no `aclose()`, needed
since `_drive()` — unlike the old bare-`_stream`-passthrough on an empty
chain — always wraps the source). `flat_map()` drops its
`collect(to_generator)` wrapper layer, iterating the inner stream's own
`._compose()` directly while keeping `aclosing()` around it, and checks
`downstream.cancellation_requested()` between pushed elements so a
downstream `.limit()` still stops it mid-inner-iteration instead of
over-pushing.

**Two scoping decisions taken (from `design.md`):** (a) push stays
internal only — `_compose()` still returns an `AsyncGenerator`, avoiding
the pull-bridge (`Spliterator`) that pushing all the way to the terminal
would need; (b) the terminal seat ships now, with one implementation
(`GeneratorBridgeSink`), rather than deferring it to the Collector
redesign.

**Benchmark (2026-08-18, this repo's dev environment, Python 3.14.5,
20,000 elements, chain of 8 `.map()` ops, best of 5):** 2,480.6 ns/element
before, 1,872.6 ns/element after — a ~24.5% gain, consistent with (and
better than) the proposal's 15–17% estimate; the bridge's buffer-and-yield
step gives back some but not all of the fully-pushed-to-terminal figure
the proposal separately measured.

The entire pre-existing test suite passed unmodified except one
internals-facing test (`test_sequential_long_chain_does_not_recurse_at_
build_time`) updated to construct fake ops with `.link()` instead of raw
closures, since `_sequential()`'s signature is now `(intermediaries,
terminal_sink) -> Sink` rather than `(intermediaries, iterable) ->
AsyncGenerator` — an intentional, documented signature change, not a
behavior regression. Added `tests/test_sink.py` covering the
`sink-protocol` spec directly (lifecycle ordering, empty source, zero/one/
many pushes per accept, pushing from `end()`, state-map lookup/fallback/
sharing, cancellation propagation, terminal `result()`). Added a direct
`to_generator()`-with-no-`aclose()`-source test (`tests/test_collect.py`)
to keep that branch covered, since `_compose()` no longer ever returns a
bare source without `aclose()` the way the old empty-chain passthrough
did. New `sink-protocol` spec; `pipeline-composition` updated to describe
state and cancellation via `begin(state_map)`/`cancellation_requested()`
instead of the old `make_state()`/`state_map` convention and `limit()`'s
self-closing upstream. No public API change; `collector.py` untouched.
See `openspec/changes/redesign-pipeline-sink-chain`.
