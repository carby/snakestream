## Why

Every intermediate/terminal op that accepts a user-supplied callable (`map`, `filter`, `peek`, `sorted`, `all_match`/`any_match`/`none_match`, etc.) repeats the same `if iscoroutinefunction(fn): await fn(...) else: fn(...)` branch at 10 sites in `stream.py`, and `all_match`/`any_match`/`none_match` are three near-identical ~12-line methods built around it. Worse, `iscoroutinefunction()` returns `False` for a callable *object* whose `__call__` is `async def` (e.g. a class-based predicate/mapper), so a call like `Stream.of([1,2,3]).map(AsyncDouble())` silently calls the sync branch, gets back an un-awaited coroutine object, and yields corrupted output with nothing louder than a `RuntimeWarning` — no exception. Consolidating the dispatch into one helper fixes the correctness bug and removes the duplication in the same change.

## What Changes

- Add `async def _maybe_await(fn, *args)` (result-based dispatch: call `fn(*args)` first, then `await` the result if `inspect.isawaitable(result)`, otherwise return it directly) so async callable objects are handled correctly regardless of how `iscoroutinefunction()` classifies them.
- Replace the 10 repeated `iscoroutinefunction()` dispatch sites in `stream.py` (`map`, `filter`, `peek`, `sorted`'s comparator, `reduce`, `find_any`, `min`/`max`, `for_each`, and the match family) with calls to `_maybe_await`.
- Collapse `all_match`/`any_match`/`none_match`'s near-identical bodies into a single shared implementation parameterized by short-circuit condition, built on `_maybe_await`.
- Leave `flat_map`'s `iscoroutinefunction()` use untouched — it rejects coroutine-returning mappers up front by design (per `roadmap.md`), which is a distinct check from result-awaiting and must not be folded into `_maybe_await`.
- **BREAKING**: none. This is an internal dispatch fix; the only externally visible change is that async-`__call__` callable objects, which previously produced silently corrupted output, now work correctly.

## Capabilities

### New Capabilities
- `callable-dispatch`: defines the contract for invoking user-supplied sync/async callables (predicates, mappers, comparators, consumers, accumulators) uniformly across all stream operations, including correct handling of async-`__call__` callable objects.

### Modified Capabilities
(none — no existing spec currently covers callable invocation semantics; `pipeline-composition` covers chain/composition state, not per-call dispatch)

## Impact

- `src/snakestream/stream.py`: `map`, `filter`, `peek`, `sorted` (comparator dispatch), `reduce`, `min`/`max` (via `_min_max`), `for_each`, `all_match`/`any_match`/`none_match`. (`find_any()` does not take a callable and is unaffected.)
- `src/snakestream/sort.py`: `_merge` now uses `_maybe_await` internally; `sorted()` always routes through `merge_sort` when a comparator is given, dropping the sync `cmp_to_key`/`list.sort()` branch (see design.md).
- New module `src/snakestream/callable_dispatch.py` holding `_maybe_await`, needed by both `stream.py` and `sort.py`.
- No public API signature changes; `type.py`'s functional-interface aliases (`Predicate`, `Mapper`, `Comparator`, `Consumer`, `Accumulator`) are unaffected.
- Test impact: existing tests for async predicates/mappers/comparators continue to pass unchanged; added `tests/test_callable_dispatch.py` covering `_maybe_await` directly and async-`__call__` callable objects across all affected operations.
