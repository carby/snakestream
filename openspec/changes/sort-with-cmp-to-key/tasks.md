## 1. Baseline

- [x] 1.1 Record the pre-change baseline: `uv run pytest` green, and note the test count and coverage figure so the post-change run can be compared against it. No test file is edited by this change, so both numbers must come out identical.
- [x] 1.2 Re-run the benchmark from proposal.md — 20,000 random floats, sync 3-way comparator, best of 5 — against the shipped `merge_sort`, and keep the number. This is the "before" half of the benchmark gate.

## 2. `sort.py` — the algorithm split

- [x] 2.1 Add the imports `sort()` needs: `cmp_to_key` from `functools`, `Any` from `typing`, and `Comparator` from `snakestream.type`. `isawaitable` and `is_async_callable` are already imported.
- [x] 2.2 Add the private `_checked(comparator)` wrapper returning a sync `compare(a, b)` that calls the comparator, inlines `if type(sign) is not int: check_comparator_result_type(sign)`, and returns the sign. The inlined test with a call-out only on the raising path is load-bearing for the measured figure, not a style choice — say so in a comment, pointing at `is_new_extremum` above it for the same trick.
- [x] 2.3 Add `async def sort(arr, comparator)` above `merge_sort`, per design.md — Decisions: async classification goes straight to `merge_sort`; otherwise, when `len(arr) > 1`, one trial `comparator(arr[0], arr[1])`, awaiting and rerouting to `merge_sort` if the result is awaitable and running `check_comparator_result_type` on it if it is not; then `arr.sort(key=cmp_to_key(_checked(comparator)))` and `return arr`.
- [x] 2.4 Annotate `sort()` and `_checked()` fully (`list[Any]`, `Comparator`, return types). Leave the rest of `sort.py` unannotated — the module-wide pass is story 5's.
- [x] 2.5 Give `sort()` a docstring covering the three things a reader will otherwise have to rediscover: why the sync path cannot use the raw comparator (`comparator-contract`'s `bool` rejection), why the trial comparison exists (`callable-dispatch`'s sync-`__call__`-returning-a-coroutine scenario, uncatchable inside `list.sort`), and that a comparator-based sort of two or more elements therefore makes one extra invocation.
- [x] 2.6 **Amended during apply, user-approved.** This task was written on a wrong premise and its original text — leave `merge_sort` byte-for-byte unchanged — could not be satisfied. Once `sort()` settles asyncness ahead of the call, *every* comparator reaching `merge_sort` returns awaitables: either `is_async_callable` said so, or the trial proved it. So `_merge`'s `elif not state[1]` ladder can never fire, and coverage caught it as two unreachable branches (`121->126`, `123->126`), dropping the gate to 97.79%. Resolved by deleting the `state` list entirely: `merge_sort` recurses into itself instead of `_merge_sort`, and `_merge` does a plain `sign = await comparator(...)`. Ten lines lighter, all 561 tests still green, and the same shape as this batch's `_ForEachSink._finish` removal — an ordering that looks load-bearing but is not. `is_new_extremum` and `check_comparator_result_type` are unchanged as written.

## 3. `ops.py` — the call site

- [x] 3.1 Change the import at `ops.py:15` from `merge_sort` to `sort`.
- [x] 3.2 In `_SortedSink.end()`, call `cache = await sort(cache, self._comparator)`.
- [x] 3.3 Replace the four-line "Always merge_sort here rather than list.sort()+cmp_to_key" comment. It is about to be false, and it is also the artefact this story is closing out — the new comment should be one or two lines saying that `sort()` owns the sync/async split, not restate the split. Do not leave the `add-maybe-await-helper` design-doc reference pointing at a decision that has been reversed.
- [x] 3.4 Leave the `reverse` handling, the `else: cache.sort()` branch, the downstream push loop and its cancellation check untouched.

## 4. Verify

- [x] 4.1 `uv run pytest` — same test count and same pass state as 1.1, **with no test file edited**. Confirm with `git status` that `tests/` is clean; a modified test here means the change went wider than the story.
- [x] 4.2 Confirm by name that the tests that pin each constraint pass: `test_sorted_comparator`, `test_sorted_async_comparator_and_reverse`, `test_sorted_matches_builtin_sorted`, `test_sorted_comparator_matches_cmp_to_key`, `test_sorted_async_comparator_matches_cmp_to_key`, `test_sorted_rejects_bool_comparator`, `test_sorted_rejects_async_bool_comparator`, `test_sorted_async_callable_object_comparator`, `test_sorted_sync_call_returning_coroutine_comparator`.
- [x] 4.3 `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src`, `uv run pytest --cov-fail-under=98`, and `openspec validate sort-with-cmp-to-key --strict`.
- [x] 4.4 Both anticipated branches came out covered by the existing suite. A third line did not: `_checked`'s `check_comparator_result_type` call, because both bool-rejection tests now raise from the *trial* comparison instead, one comparison earlier. Flagged rather than patched, per this task; user approved adding one test. `test_sorted_rejects_non_int_on_a_later_comparison` sorts `[3, 1, 2.5]` with `lambda a, b: a - b` — int for the trial pair `(3, 1)`, float once `2.5` is involved — which covers the line and pins a contract requirement the suite did not previously assert: the int contract holds for *every* comparison, not just the first. This is the only test added, and no existing test was modified.

## 5. Benchmark gate

- [x] 5.1 Re-run 1.2's benchmark against the new `sort()` and report both figures. Expect roughly 2.3x on the sync path; anything under 2x means the `_checked` wrapper's shape regressed and should be looked at before landing.
- [x] 5.2 Show the async path is unchanged: time an `async def` comparator sort before and after. It routes to the same `merge_sort` with one extra `is_async_callable` call per sort, so the figures should be within noise.
- [x] 5.3 Put both figures in the commit message. The roadmap's story-4 table is the claim; the commit is where it gets confirmed.

## 6. Close out

- [x] 6.1 Move story 4 to **Done** in `roadmap.md` with the confirmed figures, the settled safety-net decision (trial comparison, and why the narrowing was rejected), and the extra-invocation trade-off. Update the **Now** preamble: story 5 becomes next, and the "only story facing the benchmark gate" note is spent.
- [x] 6.2 Note in story 5's row that `sort.py` now holds three things, not two — `merge_sort`, the comparator semantics, and the new `sort()` dispatcher — so the rename decision has one more piece to place.
- [x] 6.3 Commit `src/`, the roadmap and the change directory together, then archive with `openspec archive sort-with-cmp-to-key`.
