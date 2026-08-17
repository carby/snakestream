## 1. Implementation

- [x] 1.1 Add `Stream.to_array()` to `src/snakestream/stream.py`, delegating to `self.collect(to_list)` (named `to_array`, snake_case, matching every other method's Java-name adaptation — `for_each`, `find_any`, `flat_map` — rather than literal `toArray`)
- [x] 1.2 Confirm no `ParallelStream` override is needed (inherits from `Stream`)

## 2. Tests

- [x] 2.1 Create `tests/test_to_array.py`: non-empty sequential stream returns expected list
- [x] 2.2 Empty stream returns `[]`
- [x] 2.3 Result equals `collect(to_list)` on an equivalent chain
- [x] 2.4 `ParallelStream.to_array()` returns all source elements (order-agnostic comparison)
- [x] 2.5 Calling `to_array()` with an argument raises `TypeError`

## 3. Docs

- [x] 3.1 Update README's `Stream` API table: mark `to_array()` implemented (`x`, alongside the other terminal ops)
- [x] 3.2 Add a row to the same table for `toArray(generator)`, struck through like the other intentionally-skipped Java-only overloads (e.g. `map_to_double`), noting it's not applicable in Python: Java's overload exists to work around the lack of runtime generic-array construction and get a correctly-typed array instead of `Object[]`; Python's `list` has no array/generic-array distinction to work around
- [x] 3.3 Remove `toArray()` and `toArray(IntFunction<A[]> generator)` from README's "Left to do" list
- [x] 3.4 Update `roadmap.md`: move item #2 to Done with implementation summary

## 4. Validation

- [x] 4.1 `uv run pytest`
- [x] 4.2 `uv run ruff check .` and `uv run ruff format --check .`
- [x] 4.3 `uv run ty check src`
