## Why

Roadmap item #2 (`roadmap.md`) flags `Stream.toArray()` as a Java Stream parity gap blocked on a design decision: Java's `toArray()` exists because arrays are a distinct, reified type from `List` and `toArray(IntFunction<A[]> generator)` exists to work around Java's lack of runtime generic-array construction. Neither motivation applies to Python — `list` is already the general-purpose ordered collection, and there is no generic-array-factory problem to solve. The decision (see conversation) is to add `to_array()` as a same-behavior alias for `collect(to_list)`, for Java-surface-API parity, and skip the `toArray(generator)` overload entirely since it has no Pythonic equivalent.

## What Changes

- Add `Stream.to_array()` — a terminal operation returning a `list` of every element pulled through the composed chain, functionally identical to `collect(to_list)`. Named `to_array` (snake_case), matching every other Java-name adaptation already in the class (`for_each`, `find_any`, `flat_map`), not the literal Java casing `toArray`.
- Do **not** add a `toArray(generator)` overload — no README "not yet implemented" line for it; instead it will be documented in README as intentionally skipped.
- Update README's parity table to mark `to_array()` implemented and `toArray(generator)` intentionally skipped, with a one-line rationale.

## Capabilities

### New Capabilities
- `stream-to-array`: Defines the contract for `Stream.to_array()`, a terminal operation aliasing `collect(to_list)`.

### Modified Capabilities
(none — no existing capability's requirements change)

## Impact

- `src/snakestream/stream.py`: add `to_array()` method to `Stream` (inherited by `ParallelStream`), delegating to the existing `collect(to_list)` path.
- `README.md`: parity table update (implemented / intentionally-skipped rows).
- New tests: `tests/test_to_array.py`.
- No breaking changes; purely additive.
