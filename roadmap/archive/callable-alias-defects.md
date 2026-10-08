+++
id = "callable-alias-defects"
title = "Fixed three `type.py` callable-alias defects found in review"
filed = 2026-08-18
closed = 2026-08-18
outcome = "shipped"
+++

Fixed three `type.py` callable-alias defects found in review: (a)
`Mapper = Callable[[T], R | None]` now includes `Awaitable[R | None]`,
matching `Predicate`/`Comparator`'s existing sync-or-async pattern and
`map()`'s actual `_maybe_await`-based dispatch, which already supported
async mappers without the type declaring it; (b) `Consumer` changed from
`Callable[[T], T]` (wrong return type — a consumer's return value is
discarded, not a `T`) to `Callable[[T], None | Awaitable[None]]`, and
`for_each()`/`for_each_ordered()` (`stream.py`), which previously inlined
their own `Callable[[T], Any]` instead of using the alias, now use
`Consumer[T]`; (c) deleted `Filterer = Callable[[T], T]`, dead code never
referenced anywhere in `src/` (`filter()` uses `Predicate`). Both alias
widenings are additive to their unions, so no previously-valid sync usage
is affected. Typing-only change, no runtime behavior differs. See
`openspec/changes/fix-type-py-callable-alias-defects`.
