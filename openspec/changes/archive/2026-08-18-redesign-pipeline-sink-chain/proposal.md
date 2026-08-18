## Why

Every intermediate operation in `stream.py` is an async generator of the shape
`async def fn(iterable): async for i in iterable: yield ...`, so the chain is
wired together by nested `async for` delegation. That shape makes each op
responsible for its own pull loop, forces stateful ops (`_DistinctOp`,
`_LimitOp`, `_SkipOp`) onto an ad-hoc "optional second positional argument"
state protocol that only they implement, and gives `collect()` no interface to
plug into — which is why the planned `Collector(supplier, accumulator,
combiner, finisher)` redesign currently reads as a second, separate redesign
rather than a follow-on.

Replacing that with a Java-style push-based `Sink` protocol
(`begin`/`accept`/`end`) fixes all three at once: `begin(shared_state)` makes
per-composition and cross-branch state first-class instead of conventional,
and `begin`/`accept`/`end` is the *same* interface a `Collector`'s
`supplier`/`accumulator`/`finisher` needs, so the Collector work becomes
"occupy the terminal seat this protocol already defines." Benchmarking
(2026-08-18, Python 3.14, 20,000 elements, chain of 8 ops) measured a
Java-faithful Sink chain at 4,806 ns/element versus 5,681 today — a 15–17%
gain — but the motivation here is architectural, not performance; the
`RecursionError` claim does **not** hold (Java's own `Sink.ChainedReference`
is equally O(k) stack-deep per element, and the ceiling only bites at chain
lengths around 1,000).

## What Changes

- **New `Sink` protocol** — an async push interface of `begin(shared_state)` /
  `accept(element)` / `end()`, plus a `cancellation_requested()` query for
  short-circuiting ops. Intermediate sinks chain by holding a `downstream`
  sink and calling `downstream.accept(...)`.
- **A terminal seat in the protocol from the start.** The protocol defines a
  terminal-sink position (a sink with no `downstream`) that accumulates and
  produces a result via `end()`. This change ships that seat and one
  implementation of it — the generator-bridge sink that `_compose()` drives —
  so the follow-on Collector redesign plugs a `Collector` into an existing
  seat rather than inventing one.
- **All eight intermediate ops reimplemented as sinks**: `filter`, `map`,
  `flat_map`, `sorted`, `peek`, `distinct`, `limit`, `skip`.
- **Push stays internal.** `_compose()` still returns an
  `AsyncGenerator[T, None]`. Pushing happens inside the chain; a bridge sink
  at the tail converts the push back into yields. All 11 terminal ops, every
  collector, `iterator()`, and `_concat` are untouched, since each is already
  `async for n in self._compose()`. No pull bridge / `Spliterator` is needed,
  so this does not depend on the parked **Later** items.
- **`make_state()` / `state_map` convention retired**, replaced by
  `begin(shared_state)`. `ParallelStream._parallel()` stops introspecting ops
  for a `make_state` attribute and instead passes one shared-state object into
  every branch's `begin()`.
- **`flat_map()` sheds its `aclosing()` / `to_generator` machinery** — pushing
  the inner stream's elements downstream removes the second-layer wrapper
  generator whose lifetime had to be managed explicitly.
- **`limit()`'s short-circuit becomes protocol-level** via
  `cancellation_requested()`, rather than the current
  `await iterable.aclose()` from inside the op.
- No public API change. Every user-visible signature, return type, and
  documented behavior in `pipeline-composition` is preserved; this is an
  internal execution-model swap. Not **BREAKING**.

## Capabilities

### New Capabilities
- `sink-protocol`: The push-based op protocol itself — `begin`/`accept`/`end`/
  `cancellation_requested` semantics, the ordering guarantees between them,
  how intermediate sinks chain to a `downstream`, what the terminal seat is
  and what it contributes, and how shared state is threaded through `begin`.

### Modified Capabilities
- `pipeline-composition`: The requirements describing *how* composition works
  change shape — the per-composition state reset and the cross-branch shared
  state for `distinct`/`limit`/`skip` are now expressed through
  `begin(shared_state)` rather than the `make_state()`/`state_map` convention,
  and `limit()`'s no-over-pull guarantee is now delivered by
  `cancellation_requested()` rather than by the op closing its own upstream.
  The observable guarantees (chain not consumed, state fresh per composition,
  parallel global correctness, `limit()` pulls at most `n`, `flat_map()`
  cleans up per-element inner streams) are all preserved, but the mechanism
  each requirement names is being replaced, so the spec text must be updated
  to match.

## Impact

- `src/snakestream/stream.py` — all eight intermediate ops rewritten;
  `_DistinctOp`/`_LimitOp`/`_SkipOp` become sinks.
- `src/snakestream/base_stream.py` — `_sequential()` builds a sink chain
  instead of nesting generators; `_compose()` drives it through the bridge
  sink.
- `src/snakestream/parallel_stream.py` — `_parallel()`'s `make_state`
  introspection replaced by shared state passed to `begin()`.
- New module for the `Sink` protocol and the bridge/terminal sinks (named for
  what it contains, per project convention).
- `src/snakestream/type.py` — any new composite/callable aliases the protocol
  needs.
- Unchanged: `collector.py`, `sort.py`, `callable_dispatch.py`,
  `stream_builder.py`, and every terminal operation.
- Tests: existing suites are the primary regression gate (behavior is
  unchanged by design); new tests cover the protocol's own contract.
- Sequencing: this lands before the `Collector(supplier, accumulator,
  combiner, finisher)` redesign, which then occupies the terminal seat
  defined here.
