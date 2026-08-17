## Why

`Stream.for_each()` makes no encounter-order guarantee, which is correct for `ParallelStream` today since its racing-branch execution model is inherently unordered. Java's `Stream` API exposes a separate `forEachOrdered()` for callers who need the consumer invoked in encounter order regardless of sequential/parallel mode. `BaseStream.unordered()`/`is_ordered()` (see roadmap Done) already exist specifically to unblock this method, and there are no remaining blockers.

## What Changes

- Add `Stream.for_each_ordered(consumer)` — like `for_each()`, but guarantees the consumer is invoked in the stream's encounter order even when called on a `ParallelStream` instance, by driving consumption through `BaseStream._sequential()` rather than the (possibly parallel) `self._compose()`.
- No change to `for_each()`'s existing (unordered-for-parallel) behavior.

## Capabilities

### New Capabilities
- `stream-foreach-ordered`: defines `for_each_ordered()`'s encounter-order guarantee for both `Stream` and `ParallelStream`, including how it differs from `for_each()`.

### Modified Capabilities
(none — `for_each()`'s existing contract is unchanged)

## Impact

- `src/snakestream/stream.py`: new `for_each_ordered()` method alongside `for_each()`.
- `tests/test_for_each.py` or a new `tests/test_for_each_ordered.py`: coverage for ordering on both `Stream` and `ParallelStream`.
- README.md: mark `forEachOrdered` as implemented per `CLAUDE.md`'s parity-tracking instruction.
- No public API removal or breaking change.
