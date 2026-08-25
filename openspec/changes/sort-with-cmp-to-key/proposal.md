## Why

`_SortedSink.end()` (`ops.py:100-108`) always routes a comparator-based sort
through `merge_sort`, and its own comment states the cost as if it were
unavoidable — *"Trades away Timsort's speed for sync comparators"*. It is
avoidable. `merge_sort` classifies the comparator with `is_async_callable`
already; only the async case actually needs a hand-written merge with an
`await` in the inner loop. The sync case can hand the comparison function to
`list.sort(key=cmp_to_key(...))` and get Timsort.

Measured on 20,000 random floats with a sync 3-way comparator, best of 5,
Python 3.14.5 — confirmed 2026-08-25 against the shipped `merge_sort`:

| Variant | time | vs. shipped |
|---|---|---|
| `merge_sort` (as shipped) | 58.4 ms | 1.00x |
| `list.sort(key=cmp_to_key(cmp))` | 16.2 ms | 3.61x |
| `list.sort(key=cmp_to_key(checked(cmp)))` | 25.2 ms | **2.32x** |

The third row is the one that ships. The `comparator-contract` spec's
"Comparators must not return bool" requirement makes `sorted()` responsible for
raising `TypeError` on a `bool` result, and `cmp_to_key` calling the raw
comparator would skip that — so the shipped shape keeps a per-comparison type
check, which is what `checked()` measures. **2.3x with the contract intact is
the number; 3.6x is not available.** This is story 4 of the 2026-08-25 batch
and the only story in it that makes the library faster rather than easier to
read.

## What Changes

- **`sort.py` gains one entry point, `sort(arr, comparator)`**, which owns the
  choice of algorithm: classify the comparator once, then either
  `arr.sort(key=cmp_to_key(...))` (sync) or `await merge_sort(arr, comparator)`
  (async). `merge_sort` stays exactly as it is, now reached only on the async
  path.
- **`_SortedSink.end()` calls `sort()`** instead of `merge_sort()`, and its
  "always merge_sort here" comment — which will no longer be true — is replaced
  by one naming the split.
- **The one-time `isawaitable` safety net is settled before the sort, not
  during it.** A comparator with a plain `def __call__` that returns a
  coroutine classifies as sync, and `list.sort` offers no per-comparison
  `await` to catch it in. `sort()` therefore makes **one trial comparison**
  ahead of the sort when the classification says sync and the buffer holds at
  least two elements; an awaitable result reclassifies the comparator as async
  and the whole sort goes to `merge_sort`. The narrowing alternative — dropping
  the safety net for `sorted()` alone — is rejected: it would break the
  `callable-dispatch` spec's "Sync-signatured callable that returns a
  coroutine" scenario and the `test_sorted_sync_call_returning_coroutine_comparator`
  test that pins it.
- No public API, no observable behaviour, no new dependency (`functools.cmp_to_key`
  is stdlib, and the codebase already used it on this exact path before
  `add-maybe-await-helper` removed the branch).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. This is a private-surface performance change: `sorted()`'s results,
stability, `reverse` handling, `TypeError` on `bool`, async-comparator support
and sync-callable-object support are all unchanged, so no requirement in
`comparator-contract` or `callable-dispatch` moves. The change sets
`skip_specs: true`, the same treatment as `tidy-stream-chain-building`,
`split-ops-into-ops-module` and `collapse-terminal-drive-loop`.

Both specs are nonetheless **constraints on the shape** rather than bystanders,
and are cited as such in design.md: `comparator-contract` forces the
per-comparison `bool` check that costs the difference between 3.6x and 2.3x,
and `callable-dispatch` forces the trial comparison.

## Impact

- `src/snakestream/sort.py` — new `sort()`; `merge_sort` untouched.
- `src/snakestream/ops.py` — `_SortedSink.end()` and its comment; the
  `merge_sort` import becomes a `sort` import.
- **No test file is edited.** Every existing `sorted()` test — the
  async-comparator, bool-rejection, callable-object, sync-`__call__`-returning-
  coroutine and `cmp_to_key`-equivalence property tests — must pass unmodified.
  That is the whole verification story, and it is also the tripwire: a test edit
  in this change means the change went wider than the story.
- `roadmap.md` — story 4 moves to **Done**; story 5 becomes next.
- Benchmark gate applies (this is the one story in the batch that carries it):
  a confirmation run must show the sync path faster by roughly the figures above
  and the async path unchanged.
