+++
id = "comparator-result-type-guard"
title = "Added a runtime guard against a `bool`-returning `Comparator`"
filed = 2026-08-11
closed = 2026-08-11
outcome = "shipped"
+++

Added a `check_comparator_result_type()` runtime guard (`sort.py`) that
raises `TypeError` if a user-supplied `Comparator` returns `bool` instead
of `int`, used by `Stream._min_max()` (backing `min()`/`max()`) and both
branches of `Stream.sorted()` (sync `cmp_to_key` path and the async
`merge_sort`/`_merge` path). Closes a gap the earlier `Comparator`
contract fix (below) didn't cover: Python's `bool` is a subclass of `int`,
so a bool-returning comparator like `lambda x, y: x > y` type-checks fine
under `ty`/mypy/pyright and previously degraded silently instead of
erroring — for `min()` it could never signal "orders before" (always
returning the first element), while `max()`'s behavior happened to be
correct by coincidence. No static-typing trick can close this gap since
it's structural to Python, not a `type.py` alias choice. Also fixed 18
pre-existing tests across `tests/test_min.py`/`tests/test_max.py` that
were passing bool comparators and only passed today via first-element
luck (`min()`) or coincidence (`max()`); added regression tests asserting
the `TypeError` for `min()`/`max()`/`sorted()`, sync and async. Tracked as
**BREAKING** in README's migration log per `CLAUDE.md`.
