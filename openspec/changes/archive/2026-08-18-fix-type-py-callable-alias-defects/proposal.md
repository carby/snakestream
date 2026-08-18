## Why

`type.py`'s callable-alias types have drifted from how they're actually used at runtime. `Mapper` doesn't declare `Awaitable`, even though `map()` fully supports async mappers via `_maybe_await`, so an async mapper's return type isn't checked correctly by `ty`. `Consumer` declares the wrong return type (`T` instead of discarding the return value) and is also missing `Awaitable`, and isn't even used consistently — `for_each()`/`for_each_ordered()` bypass it entirely with an inline `Callable[[T], Any]`. `Filterer` is dead code that duplicates `Predicate`'s job and is never referenced in `src/`. These are pure type-alias corrections with no runtime behavior change.

## What Changes

- Add `Awaitable[R | None]` to `Mapper`'s return type, matching `Predicate`/`Comparator`'s existing sync-or-async pattern.
- Fix `Consumer`'s return type from `Callable[[T], T]` to `Callable[[T], None | Awaitable[None]]`, matching its actual role as a side-effecting callback whose return value is discarded.
- Update `for_each()`/`for_each_ordered()` (`stream.py`) to use the corrected `Consumer` alias instead of their inline `Callable[[T], Any]` signatures.
- Delete `Filterer` — dead code, never referenced anywhere in `src/`.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `generic-stream-typing`: `Mapper` and `Consumer` type aliases now correctly reflect sync-or-async callable support, so `ty` catches type errors on async mappers/consumers that it previously missed.

## Impact

- `src/snakestream/type.py`: `Mapper`, `Consumer` signatures corrected; `Filterer` removed.
- `src/snakestream/stream.py`: `for_each()`/`for_each_ordered()` signatures updated to use `Consumer`.
- No runtime behavior changes; no public API removal (`Filterer` was never exported/used).
