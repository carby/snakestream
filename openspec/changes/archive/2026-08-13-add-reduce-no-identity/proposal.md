## Why

`Stream.reduce(identity, accumulator)` requires callers to supply an identity value even when there isn't a natural one (e.g. reducing with a comparison-only accumulator, or when the identity would need to be an out-of-band sentinel). Java's `Stream<T>.reduce(BinaryOperator<T>)` covers this by folding over the stream itself and returning `Optional<T>`, empty only when the stream is empty. Snakestream's roadmap (`roadmap.md`, Now #1) has this as the next item to pick up; it's next in line since it has no blockers and can build directly on the existing 2-arg `reduce()`.

## What Changes

- Add a 1-arg overload `Stream.reduce(accumulator)` that folds the stream using its own first element as the seed, with no external identity.
- Empty-stream return: follows the existing `find_any()`/`max()`/`min()` convention in `stream.py` (`T | None`, not a wrapped `Optional` type) rather than introducing a new `Optional`-style container — returns `None` when the stream is empty.
- Delegates to the existing 2-arg `reduce(identity, accumulator)` internally by pulling the first element as the identity, so the accumulator dispatch (sync/async) logic is not duplicated.

## Capabilities

### New Capabilities
- `reduce-without-identity`: Defines the contract for the 1-arg `Stream.reduce(accumulator)` overload — seeding from the stream's own first element, empty-stream behavior, and single-element behavior.

### Modified Capabilities
(none — the existing 2-arg `reduce(identity, accumulator)` behavior is unchanged)

## Impact

- `src/snakestream/stream.py`: add the new `reduce()` overload (or extend the existing method to detect arity/accept an optional identity).
- `src/snakestream/type.py`: `Accumulator` type alias may need reuse/checking against the no-identity signature.
- `tests/test_reduce.py` (or new `tests/test_reduce_no_identity.py`): coverage for empty stream, single-element stream, multi-element stream, sync and async accumulators.
- `README.md`: update Java Stream API parity tracking to mark `reduce(BinaryOperator)` as implemented.
