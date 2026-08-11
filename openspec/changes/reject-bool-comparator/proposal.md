## Why

`Comparator` (`type.py:16`) is typed `Callable[[T, T], int | Awaitable[int]]`, but Python's `bool` is a subclass of `int`, so a bool-returning comparator like `lambda x, y: x.id > y.id` satisfies that type under `ty`/mypy/pyright without ever producing a negative value — silently violating the 3-way sign contract `sorted()`/`min()`/`max()` all depend on (see `openspec/specs/comparator-contract/spec.md`). No static-typing change can catch this, since it's structural to Python (unlike Java, where `Comparator<T>.compare()` must return primitive `int` and a boolean-returning lambda is a compile error). Two existing tests (`test_find_min_value_object_comparator` in `tests/test_min.py:91`, `test_find_max_value_object_comparator` in `tests/test_max.py:91`) already pass a bool comparator and only pass today because the first list element happens to already be the min/max — false positives that don't verify correct behavior.

## What Changes

- Add a runtime guard in `Stream._min_max()` and `Stream.sorted()` that rejects a comparator whose return value is `bool` (`isinstance(sign, bool)`), raising `TypeError` with a message pointing at the 3-way `int` contract.
- **BREAKING**: any caller currently passing a bool-returning comparator to `min()`, `max()`, or `sorted()` will now get an immediate `TypeError` instead of silently wrong (or accidentally correct) results.
- Fix `test_find_min_value_object_comparator` (`tests/test_min.py:91`) and `test_find_max_value_object_comparator` (`tests/test_max.py:91`) to use proper 3-way comparators (e.g. `lambda x, y: x.id - y.id`).
- Fix an additional 16 pre-existing tests across `tests/test_min.py` and `tests/test_max.py` that also pass bool comparators (discovered during implementation — nearly every test in both files predates the 3-way-comparator fix in commit `4f526bb` and was never migrated) to use 3-way `int` comparators instead.
- Add regression tests asserting `TypeError` is raised for bool comparators passed to `min()`, `max()`, and `sorted()` (sync and async comparator variants).

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `comparator-contract`: adds a requirement that `sorted()`, `min()`, and `max()` actively reject a comparator that returns `bool` at runtime, rather than silently accepting it as if it were a valid 3-way `int` result.

## Impact

- `src/snakestream/stream.py`: `_min_max()` and `sorted()` gain a bool-rejection check on the comparator's return value.
- `tests/test_min.py`, `tests/test_max.py`, `tests/test_sorted.py` (or equivalent): fix the two false-positive tests; add new tests for the `TypeError` guard.
- `README.md`: migration log entry per `CLAUDE.md` for the breaking behavior change.
- `roadmap.md`: move the top **Now** item to **Done** once implemented.
