## Why

`Stream.min(comparator)`/`max(comparator)`/`reduce(...)` already implement the
reduction logic Java exposes as `Collectors.min_by`/`max_by`/`reducing` — but
only as terminal-op methods, not as `collect()`-compatible collectors. That
blocks using a min/max/reduce as a *downstream* collector (e.g. inside
`groupingBy(classifier, max_by(cmp))`), which is the next roadmap item after
this one. Exposing them now is mechanical: no new reduction logic, just the
same `_min_max`/fold logic re-shaped into `collector.py`'s existing
factory-returns-closure pattern (`joining`, `counting`, `summing_*`).

## What Changes

- Add `min_by(comparator)` / `max_by(comparator)` (`collector.py`) — collectors
  returning `T | None` (`None` for an empty stream), same 3-way-int
  `Comparator` contract and first-element-wins tie-break as `Stream.min()`/
  `max()`, including the `TypeError` guard on a bool-returning comparator.
- Add `reducing(...)` (`collector.py`) with the same three overload shapes as
  Java's `Collectors.reducing`:
  - `reducing(binary_operator)` → `T | None`, no identity, `None` for an
    empty stream (mirrors `Stream.reduce(accumulator)`).
  - `reducing(identity, binary_operator)` → `T` (mirrors
    `Stream.reduce(identity, accumulator)`).
  - `reducing(identity, mapper, binary_operator)` → `R`, maps each element
    before folding (no existing `Stream` terminal op covers this third
    overload today).
- Update README's `Collectors` table with the new rows.

## Capabilities

### New Capabilities
- `collector-min-max`: `min_by`/`max_by` collector factories wrapping
  `Stream.min`/`max`'s comparator-based extremum logic for use with
  `collect()`.
- `collector-reducing`: `reducing(...)` collector factories wrapping
  `Stream.reduce`'s fold logic (all three Java overload shapes) for use with
  `collect()`.

### Modified Capabilities
(none — no existing requirement changes)

## Impact

- `src/snakestream/collector.py`: new `min_by`, `max_by`, `reducing` functions.
- `src/snakestream/type.py`: none expected (existing `Comparator`,
  `BinaryOperator`, `Accumulator`, `Mapper` aliases already cover the needed
  shapes).
- `README.md`: `Collectors` table gets three new rows.
- New tests: `tests/test_min_by.py`, `tests/test_max_by.py`,
  `tests/test_reducing.py`.
- No breaking changes; purely additive.
