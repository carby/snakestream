## Why

`type.py` declares `Comparator = Callable[[T, T], bool | Awaitable[bool]]`, but `sorted()` treats it as a Java-style 3-way *int* comparator (`sort.py` does `await comparator(...) <= 0`, and `stream.py` feeds it to `cmp_to_key`), while `min()`/`max()` treat it as a *bool* predicate (`stream.py` does `if comparator(n, found)`, negating for `min()`). Java's own `Stream.min(Comparator)`/`max(Comparator)` take the exact same 3-way `Comparator<T>` as `sorted()` — there is only ever one comparator contract in Java's Stream API, and `min`/`max` simply check the sign of `compare()`. Snakestream's `min()`/`max()` deviate from that by expecting a bool, and the type alias doesn't say so either way — so both directions currently fail silently, with no exception and no `ty` error: a 3-way comparator passed to `max()` gives `max([3,1,2]) -> 2` instead of `3`, and a bool comparator passed to `sorted()` returns the input unsorted.

## What Changes

- Keep a single `Comparator` alias, corrected to `Callable[[T, T], int | Awaitable[int]]` (3-way, matching Java and `sorted()`'s existing usage).
- Fix `Stream.min()`/`Stream.max()`/`Stream._min_max()` in `stream.py` to interpret `comparator(x, y)` by the sign of its return value (as `sorted()` already does), instead of treating it as a bool.
- Fix `min()`'s tie-break as part of the same logic change: it must return the first of equal elements (matching `max()`'s behavior), not the last.
- Update README's parity table and the pre-1.0 migration log per `CLAUDE.md` to record the corrected `Comparator` contract and any `min()`/`max()` call-site impact for existing bool-style comparator callers (**BREAKING** for any caller currently passing a bool-returning comparator to `min()`/`max()`).

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `comparator-contract` (new spec, no prior spec file existed for this behavior): defines the single 3-way int comparator contract shared by `sorted()`, `min()`, and `max()`, and `min()`'s tie-break behavior.

## Impact

- `src/snakestream/type.py`: `Comparator` alias corrected to `int`-returning.
- `src/snakestream/stream.py`: `min()`/`max()`/`_min_max()` logic fixed to use comparator sign; tie-break fix.
- `src/snakestream/sort.py`: no change (already assumes 3-way int contract correctly).
- `README.md`: migration log entry, any type references.
- Tests: `tests/test_min.py`, `tests/test_max.py` (or equivalents) need cases asserting the corrected contract and tie-break behavior.
