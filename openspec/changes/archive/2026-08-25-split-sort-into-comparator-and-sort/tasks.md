## 1. Confirm the tripwire before touching anything

- [x] 1.1 Re-run the grep the roadmap row calls for, since `sort.py` changed under story 4: `grep -rn "snakestream.sort\|merge_sort\|is_new_extremum\|check_comparator_result_type" tests/ README.md openspec/specs/` must return **zero** hits. If it returns any, stop — the story's "touches no test" premise no longer holds and the plan needs revisiting rather than adapting.
- [x] 1.2 Record the baseline the move must preserve: run `uv run pytest` and keep the test count and the coverage percentage (expected 562 green, 98.05%). This is the instrument for "it was really just a move" — see design.md — Risks.

## 2. Create `comparator.py`

- [x] 2.1 Create `src/snakestream/comparator.py` with `check_comparator_result_type` then `is_new_extremum`, moved **verbatim** from `sort.py:10-34` — same names, same signatures, same bodies, same docstring, same order.
- [x] 2.2 Give it only the imports those two need: nothing. Neither function imports anything today (`is_new_extremum` calls `check_comparator_result_type` in the same module), so the new module has an empty import block. Do not add `from __future__ import annotations` for its own sake — match whichever convention the sibling modules of this size use.
- [x] 2.3 Leave `is_new_extremum`'s docstring untouched, including its `check_comparator_result_type()` reference, which is still same-module and still true.

## 3. Reduce `sort.py` to sorting

- [x] 3.1 Delete `check_comparator_result_type` and `is_new_extremum` from `sort.py`, leaving `_checked`, `sort`, `merge_sort`, `_merge` in their current relative order.
- [x] 3.2 Add `from snakestream.comparator import check_comparator_result_type` to `sort.py`. `is_new_extremum` is **not** imported — nothing in `sort.py` calls it; if `ruff` flags it as unused, it was added by mistake.
- [x] 3.3 Fix the one docstring phrase the split falsifies: `_checked`'s "the same trick is_new_extremum uses above" — `is_new_extremum` is no longer above, it is in `comparator.py`. Correct the location only; keep the rest of the sentence, which explains a still-load-bearing perf decision. Per design.md — Decision 3, this is the **only** docstring edit in the change.
- [x] 3.4 Verify nothing else moved: `sort()`'s docstring, `_checked`'s body, `merge_sort` and `_merge` are otherwise byte-for-byte what they were.

## 4. Annotate the two bare functions

- [x] 4.1 Annotate `merge_sort` and `_merge` with `list[Any]` parameters and return. **Amended during apply:** the comparator parameter is `AsyncComparator`, not `Comparator` — see 4.2.
- [x] 4.2 **Amended during apply, user-approved. This task was written on a wrong premise and could not be satisfied as written.** It said to use `Comparator` as-is because the union is a safe supertype. It is not: `_merge` awaits the comparator unconditionally, so `Comparator` makes the await a `ty` error (`invalid-await: int | Awaitable[int] is not awaitable`, `sort.py:87`). While the functions were bare, `ty` inferred nothing and stayed silent; annotating is what surfaced it. Resolved by adding `AsyncComparator = Callable[[T, T], Awaitable[int]]` to `type.py` beside `Comparator`, annotating both functions with it, and passing `cast("AsyncComparator", comparator)` at `sort()`'s two reroute sites — where `is_async_callable` or the trial comparison has just proved the narrowing. This makes `type.py` a fourth touched file, which the design excluded; accepted because a composite callable type belongs in `type.py` rather than inline. The rejected alternative was `cast("Awaitable[int]", ...)` inside `_merge`'s loop, which states the narrowing at the least informative point and puts a cast on the per-comparison path.
- [x] 4.3 Confirm `uv run ty check src` passes and that no function in `src/snakestream/` is left unannotated.

## 5. Retarget the three import sites

- [x] 5.1 `src/snakestream/terminals.py:9` — change `from snakestream.sort import is_new_extremum` to `from snakestream.comparator import is_new_extremum`. Keep the import block's existing ordering convention (it sits between `sink` and `type`; `comparator` may need to move within the block).
- [x] 5.2 `src/snakestream/collector.py:11` — the same change, same ordering care.
- [x] 5.3 `src/snakestream/ops.py:15` — **no change.** `from snakestream.sort import sort` is still correct. Confirm it, and confirm `_SortedSink.end()`'s comment naming `sort.py` is still accurate (design.md — Decision 2 treats this as the check that `sort()` landed on the right side).
- [x] 5.4 Run the design's stated check: `grep -rn "from snakestream.sort import" src/` returns exactly one line, `ops.py:15`.

## 6. Verify the move changed nothing

- [x] 6.1 `uv run pytest` — 562 green, **no test file modified**. A test edit anywhere is the story's tripwire: stop and flag it rather than absorbing it.
- [x] 6.2 `uv run pytest --cov-fail-under=98` — coverage at the 1.2 baseline. A pure move cannot shift it; drift means something other than a move happened.
- [x] 6.3 `uv run ruff check .` and `uv run ruff format --check .` pass. In particular ruff must report no unused import in `sort.py`, `terminals.py` or `collector.py`.
- [x] 6.4 `openspec validate split-sort-into-comparator-and-sort --strict` passes with `skip_specs: true` and no delta specs.
- [x] 6.5 Sanity-check the package still imports from a clean interpreter: `uv run python -c "import snakestream"`. Catches a circular import between the two new modules, which the suite's own import order might mask.

## 7. Close the story out

- [x] 7.1 Move story 5 from **Now** to **Done** in `roadmap.md`, recording what the row left open and how it was answered: two modules rather than one, and `sort()` landing in `sort.py` on the seam-goes-with-the-caller rule, with `ops.py:15` needing no edit as the confirmation.
- [x] 7.2 Update the **Now** section's preamble, which currently says two stories remain and sequences story 5 as next. After this lands only story 6 remains, and it is independent — the "dependency order" framing no longer applies to a single item.
- [x] 7.3 Note in the Done entry that the annotation work (task group 4) was assumed into scope rather than confirmed with the user, and that `Comparator`'s missing narrowed alias is a loose thread `type.py` could pick up later.
- [x] 7.4 Do **not** update `README.md` — module layout is not documented there — and do not rewrite the historical `merge_sort`/`sort.py` references in archived changes or in `roadmap.md`'s Done entries. They describe what was true at the time.
