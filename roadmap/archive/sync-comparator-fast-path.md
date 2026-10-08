+++
id = "sync-comparator-fast-path"
title = "The sync-comparator fast path"
filed = 2026-08-25
closed = 2026-08-25
outcome = "shipped"
+++

**The sync-comparator fast path** (2026-08-25). Story 4 of the 2026-08-25
batch, and the only one in it that makes the library faster rather than
easier to read.

`_SortedSink.end()` routed every comparator-based sort through `merge_sort`,
and its own comment stated the cost as if unavoidable — *"Trades away
Timsort's speed for sync comparators"*. Only the async case actually needs a
hand-written merge with an `await` in its inner loop. `sort.py` gained one
entry point, `sort(arr, comparator)`, which owns the choice: sync comparators
now go to `list.sort(key=cmp_to_key(...))`, async ones to `merge_sort`.
`_SortedSink.end()` calls `sort()` and says so in two lines instead of five.

**Confirmed figures**, 20,000 random floats, sync 3-way comparator, best of
9, Python 3.14.5: **69.4 ms -> 38.7 ms end-to-end through `sorted()`
(1.8x)**, and **58.4 ms -> 27.5 ms measuring the sort alone (2.1x)**. The
end-to-end number is the smaller one because the pipeline's own per-element
cost is unchanged and now dominates a larger share. The async path is
unaffected: 6.7 ms -> 6.8 ms on a 2,000-element async-comparator sort, within
noise.

**The 3.6x the proposal's table showed is not available, and the reason is a
spec.** `comparator-contract`'s "Comparators must not return bool" makes
`sorted()` responsible for raising `TypeError` on a `bool` result. A `bool`
compares perfectly well under `cmp_to_key` — it is an `int` — so handing it
the raw comparator would silently produce a wrong order instead of raising.
`_checked()` keeps a per-comparison type test, inlined with a call-out only
on the raising path, the same trick `is_new_extremum` already uses one
function up. **1.3x is the price of the contract; the contract wins.**

**The open question the roadmap left for this story — the one-time
`isawaitable` safety net — was answered with a trial comparison.** A
comparator with a plain `def __call__` returning a coroutine classifies as
sync, and `list.sort` is sync all the way down, so a coroutine seen mid-sort
cannot be awaited from inside the key function. `sort()` therefore makes one
trial `comparator(arr[0], arr[1])` before the sort when classification says
sync and the buffer holds two or more elements; an awaitable result is
awaited (so nothing is left un-awaited) and the whole sort reroutes to
`merge_sort`. The alternative the notes floated — documenting a narrowing for
`sorted()` alone — was **rejected**: it would break `callable-dispatch`'s
"Sync-signatured callable that returns a coroutine" scenario, which names no
operation and so covers `sorted()`, and the
`test_sorted_sync_call_returning_coroutine_comparator` test that pins it.
The cost is one extra comparator invocation per comparator sort of two or
more elements; nothing constrains the invocation count, and nothing could,
since Timsort and merge sort make different numbers of comparisons on the
same input anyway.

**Beyond the story as written: `merge_sort` lost its `state` list, and
branch coverage is what found it.** The plan said to leave `merge_sort`
byte-for-byte alone. That could not hold — once `sort()` settles asyncness
ahead of the call, *every* comparator reaching `merge_sort` returns
awaitables, either because `is_async_callable` said so or because the trial
proved it, so `_merge`'s `elif not state[1]` ladder can never fire. The
suite stayed green and said nothing; the `branch-coverage-gate` at 98% is
what caught it, as two unreachable arms dropping the total to 97.79%. The
ladder and the `state` list are gone, `merge_sort` recurses into itself
rather than into a `_merge_sort` that existed only to thread state, and
`_merge` does a plain `await comparator(...)`. Ten lines lighter, and it now
says what is true — *this function is the async path* — where the surviving
ladder said the opposite. Same removal this batch made to
`_ForEachSink._finish`.

**One test added, no test modified.** Both bool-rejection tests now raise
from the trial comparison, one comparison earlier, which left `_checked()`'s
own `TypeError` line uncovered. `test_sorted_rejects_non_int_on_a_later_comparison`
sorts `[3, 1, 2.5]` with `lambda a, b: a - b` — `int` for the trial pair
`(3, 1)`, `float` once `2.5` is involved — covering the line and pinning a
contract requirement the suite never asserted: the `int` contract holds for
*every* comparison, not just the first.

562 tests green, 98.05% coverage. `ruff`, `ruff format --check`,
`ty check src` and `openspec validate --strict` all pass. No spec impact —
`skip_specs: true`, since `sorted()`'s results, stability, `reverse`
handling, `bool` rejection and async support are all unchanged. See
`openspec/changes/sort-with-cmp-to-key`.
