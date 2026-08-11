## Context

`Comparator` (`type.py:16`) is currently typed as `Callable[[T, T], bool | Awaitable[bool]]`. `sorted()` (`stream.py:121-148`) already treats it correctly as a 3-way int comparator: the sync branch does `cache.sort(key=cmp_to_key(comparator))` and the async branch's `merge_sort`/`_merge` (`sort.py`) does `await comparator(left[i], right[j]) <= 0`. `min()`/`max()`/`_min_max()` (`stream.py:222-252`) instead treat it as a bool predicate: `max()` calls `_min_max(comparator)` directly and updates `found` whenever `comparator(n, found)` is truthy; `min()` wraps it in a `negative_comparator` that negates the bool and delegates to the same `_min_max`.

Since the type alias's declared contract (bool) matches neither `sorted()`'s actual usage nor Java's `Stream<T>.min/max(Comparator<? super T>)` (which reuse the same 3-way `Comparator` as `sorted`/`Collections.sort`), the fix aligns `min()`/`max()` with `sorted()` and with Java, rather than introducing a second alias.

## Goals / Non-Goals

**Goals:**
- One `Comparator` alias, 3-way int contract, used identically by `sorted()`, `min()`, and `max()` — matching Java.
- `min()`/`max()` correctly interpret the sign of `comparator(x, y)`.
- `min()` and `max()` both keep the *first* of equal (tied) elements, matching Java's behavior of only updating the running result on a strict comparison result.

**Non-Goals:**
- No new type alias (e.g. no `BiPredicate`) — Java doesn't use one for comparison, so we don't either.
- Not touching `sorted()`'s implementation — it's already correct against the 3-way contract.
- Not touching the chain-mutation or `limit()` findings tracked separately in `roadmap.md`.

## Decisions

- **Fix `type.py`**: change `Comparator = Callable[[T, T], bool | Awaitable[bool]]` to `Comparator = Callable[[T, T], int | Awaitable[int]]`.
- **Rewrite `_min_max` callers instead of the negation-wrapper trick**: drop `min()`'s `negative_comparator` closures entirely. Instead, `_min_max` takes an explicit `keep_if_positive: bool` (or `max`/`min` each build their own condition):
  - `max()`: update `found = n` when `comparator(n, found) > 0`.
  - `min()`: update `found = n` when `comparator(n, found) < 0`.
  - Alternative considered: keep the negation wrapper but negate correctly (`comparator(x, y) > 0` becomes `<`); rejected because it still routes through an inverted double-negative that's harder to read than two direct sign checks, and the wrapper closures are no longer needed once `_min_max` takes a direction.
- **Tie-break falls out for free**: using strict `>`/`<` instead of truthy bool means a tie (`comparator(n, found) == 0`) never replaces `found`, so both `min()` and `max()` naturally keep the first-seen element on ties — no separate tie-break logic needed.

## Risks / Trade-offs

- [Any existing caller currently passing a bool-returning comparator to `min()`/`max()` will silently get wrong results after this fix flips the interpretation] → This is the correctness fix itself (the old behavior was already wrong); document as **BREAKING** in README's migration log per `CLAUDE.md` so callers know to switch to 3-way comparators.
- [Callers relying on the old (undocumented, buggy) last-wins tie-break for `min()`] → Unlikely to be intentional since it wasn't documented as behavior; call out in migration log.

## Migration Plan

1. Fix `type.py` alias.
2. Fix `stream.py` `min()`/`max()`/`_min_max()`.
3. Add/update tests asserting 3-way comparator contract and first-wins tie-break for both `min()` and `max()`.
4. Update README parity table and migration log.

No runtime migration needed beyond the code change — this is a library, not a deployed service.

## Open Questions

None.
