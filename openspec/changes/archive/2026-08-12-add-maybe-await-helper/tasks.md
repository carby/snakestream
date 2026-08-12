## 1. Helper

- [x] 1.1 Add `async def _maybe_await(fn, *args)` — implemented in a new `callable_dispatch.py` module (not inline in `stream.py`) so `sort.py` could use it too without a circular import; calls `fn(*args)`, then `return await result if inspect.isawaitable(result) else result`.
- [x] 1.2 Add unit tests for `_maybe_await` directly: sync function, async function, sync callable object, async callable object (`tests/test_callable_dispatch.py`).

## 2. Replace dispatch sites in stream.py

- [x] 2.1 `filter()`: replaced `iscoroutinefunction()` branch with `_maybe_await`.
- [x] 2.2 `map()`: replaced `iscoroutinefunction()` branch with `_maybe_await`.
- [x] 2.3 `sorted()` comparator dispatch: turned out not to fit the call-then-await shape — its `iscoroutinefunction()` check picks between two different sort algorithms rather than gating a single await. Resolved (per user decision) by moving `sort.py`'s `_merge` onto `_maybe_await` internally and always routing through `merge_sort` when a comparator is given, dropping the `cmp_to_key`/`list.sort()` branch. See design.md's Decisions section, updated accordingly.
- [x] 2.4 `peek()` consumer dispatch: replaced `iscoroutinefunction()` branch with `_maybe_await`.
- [x] 2.5 `reduce()` accumulator dispatch: replaced `iscoroutinefunction()` branch with `_maybe_await`.
- [x] 2.6 `for_each()` consumer dispatch: replaced `iscoroutinefunction()` branch with `_maybe_await`.
- [x] 2.7 `min`/`max` (`_min_max`) comparator dispatch: replaced `iscoroutinefunction()` branch with `_maybe_await`, kept `check_comparator_result_type()` guard (removed now-unused `ty: ignore` comments since `_maybe_await`'s typing let `ty` narrow correctly).
- [x] 2.8 `find_any()`: no-op — on inspection `find_any()` takes no callable and never used `iscoroutinefunction()`; this task was based on a mistaken assumption in the original task list.
- [x] 2.9 `flat_map()`'s `iscoroutinefunction(flat_mapper)` check left untouched; added a short comment clarifying it's a pre-call rejection, not a dispatch site.

## 3. Collapse all_match/any_match/none_match

- [x] 3.1 Implemented shared `async def _match(self, predicate, short_circuit_on, default)` built on `_maybe_await`.
- [x] 3.2 `all_match()` rewritten as a thin wrapper over `_match` (short-circuit on `False`, default `True`).
- [x] 3.3 `any_match()` rewritten as a thin wrapper over `_match` (short-circuit on `True`, default `False`).
- [x] 3.4 `none_match()` rewritten as `not await self._match(predicate, short_circuit_on=True, default=False)`.
- [x] 3.5 Confirmed existing async-predicate short-circuit tests for all three still pass unchanged.

## 4. Regression tests for the async-callable-object bug

- [x] 4.1 Added test fixtures (`tests/test_callable_dispatch.py`): classes with `async def __call__` usable as predicate/mapper/consumer/accumulator/comparator.
- [x] 4.2 Added regression tests for `map()`, `filter()`, `peek()`, `reduce()`, `for_each()`, `sorted()`, `min()`/`max()`, and `all_match`/`any_match`/`none_match` using async-`__call__` callable objects.

## 5. Verification

- [x] 5.1 `uv run pytest` — 168 passed.
- [x] 5.2 `uv run pytest --cov-fail-under=98` — 100% coverage, gate passes.
- [x] 5.3 `uv run ruff check .` and `uv run ruff format --check .` — both clean.
- [x] 5.4 `uv run ty check src` — clean (removed one now-unused `ty: ignore` comment surfaced by the refactor).
- [x] 5.5 Updated `roadmap.md`: moved the `_maybe_await` item from **Now** to **Done**, including the `sorted()`/`sort.py` deviation.
