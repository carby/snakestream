+++
id = "await-if-needed-dispatch"
title = "Replaced the repeated `iscoroutinefunction` dispatch pattern"
filed = 2026-08-12
closed = 2026-08-12
outcome = "shipped"
+++

Replaced the repeated `if iscoroutinefunction(x): await x(...) else: x(...)`
dispatch pattern (10 sites across `filter`, `map`, `sorted`'s comparator,
`peek`, `reduce`, `for_each`, `min`/`max` via `_min_max`, and the
`all_match`/`any_match`/`none_match` family) with a single
`async def _maybe_await(fn, *args)` helper in a new
`callable_dispatch.py`, which calls first and awaits the result only if
`inspect.isawaitable(result)`. Fixes a real bug: `iscoroutinefunction()`
is `False` for a class instance with an `async def __call__`, so passing
such a callable object as a predicate/mapper/etc. previously produced an
un-awaited coroutine flowing downstream as if it were a real value, with
only a `RuntimeWarning` — no exception. `flat_map`'s existing
`iscoroutinefunction()` check, which *rejects* coroutine-returning
mappers up front, is a distinct pre-call classification and was left
untouched. Also collapsed `all_match`/`any_match`/`none_match`'s three
near-identical bodies into one shared `_match(predicate, short_circuit_on,
default)` helper built on `_maybe_await`.

`sorted()`'s comparator dispatch turned out not to fit the same
call-then-await shape: its `iscoroutinefunction()` check picks between
two different sort algorithms (`merge_sort`, which unconditionally
awaits the comparator, vs. `list.sort()` with a sync `cmp_to_key`
wrapper) rather than gating a single await. Fixed by moving `_merge`
(`sort.py`) onto `_maybe_await` internally and always routing `sorted()`
through `merge_sort` when a comparator is given, dropping the
`cmp_to_key`/`list.sort()` branch entirely — this also closes the same
async-callable-object gap for `sorted()`/`min()`/`max()`. Added
regression tests (`tests/test_callable_dispatch.py`) covering
`_maybe_await` directly (sync/async function, sync/async callable
object) and each affected operation with an async-`__call__` callable
object.
