## Why

`Stream.limit(n)` (keep the first `n` elements) is implemented, but its natural
counterpart `Stream.skip(n)` (drop the first `n` elements) is not — a gap in
Java `Stream` parity that the roadmap lists as the next item to pick up, with
no blockers and a design that can mirror `limit()`'s existing short-circuit
pattern directly.

## What Changes

- Add `Stream.skip(n)` — an intermediate operation that drops the first `n`
  elements of the stream and yields the rest, symmetric with the existing
  `limit(n)`.
- Implemented as a stateful closure (`_SkipOp`, alongside `stream.py`'s
  existing `_LimitOp`/`_DistinctOp`) exposing `make_state()` so it gets fresh
  per-composition state under `Stream` and shared, globally-correct state
  across racing branches under `ParallelStream`, following the same contract
  `pipeline-composition` already defines for `limit()`/`distinct()`.
- Update README's Java `Stream` API parity table to mark `skip(n)` as
  implemented.

## Capabilities

### New Capabilities
(none — this extends the existing pipeline-composition capability's
stateful-op contract to a new op, rather than introducing a new capability
area)

### Modified Capabilities
- `pipeline-composition`: extends the "stateful closures reset per
  composition" and "parallel state remains globally correct across branches"
  requirements, currently scoped to `distinct()`/`limit()`, to also cover the
  new `skip()` op.

## Impact

- `src/snakestream/stream.py`: new `_SkipOp` class, new `Stream.skip(n)`
  method appended to `self._chain`.
- `src/snakestream/parallel_stream.py`: no code change expected — its
  `make_state()`-based shared-state wiring is already generic across ops.
- `README.md`: parity table update (`skip(n)` implemented).
- `roadmap.md`: move `Stream.skip(n)` from Now to Done once complete.
