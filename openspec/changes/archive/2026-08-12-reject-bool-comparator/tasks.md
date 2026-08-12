## 1. Runtime guard

- [x] 1.1 Added `check_comparator_result_type(value)` in `sort.py`: raises `TypeError` (generic message, no op name) if `type(value) is not int` — rejects `bool` since it's a distinct type from `int` under `type() is` even though `isinstance(bool, int)` is true.
- [x] 1.2 `Stream._min_max()`'s `compare()` helper (`stream.py`) now assigns `sign` on its own line, calls `check_comparator_result_type(sign)`, then returns it.
- [x] 1.3 `Stream.sorted()`'s sync branch (`stream.py`) wraps `comparator` in a local `checked_comparator` that checks the sign before returning it, passed to `cmp_to_key()`.
- [x] 1.4 `sort.py`'s `_merge()` (async branch, used by `merge_sort()`) checks the sign on its own line right after `await comparator(...)`.

## 2. Fix false-positive tests

- [x] 2.1 Updated `test_find_min_value_object_comparator` (`tests/test_min.py`) to `lambda x, y: x.id - y.id`.
- [x] 2.2 Updated `test_find_max_value_object_comparator` (`tests/test_max.py`) to `lambda x, y: x.id - y.id`.
- [x] 2.3 Updated all 16 additional pre-existing bool-comparator tests in `tests/test_min.py`/`tests/test_max.py` to 3-way `int` comparators (`x - y`, `len(x) - len(y)`).
- [x] 2.4 Re-ran the updated tests via `uv run pytest tests/test_min.py tests/test_max.py` — all pass with the same expected values as before.

## 3. Regression tests

- [x] 3.1 Added `test_find_min_value_rejects_bool_comparator` (`tests/test_min.py`) asserting `TypeError`.
- [x] 3.2 Added `test_find_max_value_rejects_bool_comparator` (`tests/test_max.py`) asserting `TypeError`.
- [x] 3.3 Added `test_sorted_rejects_bool_comparator` (`tests/test_sorted.py`) asserting `TypeError`.
- [x] 3.4 Added async variants: `test_find_min_value_rejects_async_bool_comparator`, `test_find_max_value_rejects_async_bool_comparator`, `test_sorted_rejects_async_bool_comparator`.
- [x] 3.5 Already covered by existing `test_find_min_value_three_way_comparator`, `test_find_max_value_three_way_comparator`, and `test_sorted_comparator`/`test_sorted_comparator_matches_cmp_to_key` — all use proper 3-way `int` comparators and continue to pass unaffected.

## 4. Docs

- [x] 4.1 Added a migration log entry to README.md documenting the breaking `TypeError` behavior.
- [x] 4.2 Moved the item from roadmap.md's **Now** section to **Done**, summarizing what was fixed.

## 5. Verification

- [x] 5.1 `uv run pytest` — 145 passed.
- [x] 5.2 `uv run ruff check .` and `uv run ruff format --check .` — clean.
- [x] 5.3 `uv run ty check src` — clean.
- [x] 5.4 `uv run pytest --cov-fail-under=98` — 100% coverage, gate passed.
