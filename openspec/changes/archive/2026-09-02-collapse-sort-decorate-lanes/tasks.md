## 1. Establish the baseline

- [x] 1.1 Record the pre-change baseline: run `uv run pytest` and note the pass count, the `TOTAL` coverage percentage **and the per-file figure for `src/snakestream/sort.py`**, so the gates in section 4 compare against numbers rather than impressions. The per-file figure is the one that matters here — design.md, Risks, records that `sort-with-cmp-to-key` found a silently-unreachable arm this way
- [x] 1.2 Write the `itemgetter` A/B harness (single-segment scalar keys and two-segment tuple keys, 20,000 elements, best of 7) and re-establish the baseline column on this machine against **unmodified** `sort.py`; verify the lambda figures land near 3.35 ms / 5.88 ms. Keep the script for task 4.4
- [x] 1.3 Confirm the no-test-change claim before touching anything: `grep -rn "_column\|_sort_by_key\|_segment_column\|_Descending\|_tolerant_column\|merge_sort\|snakestream\.sort" tests/` must return only the comment at `tests/test_sorted.py:189` (proposal.md, Impact)

## 2. `_column()`: three re-interleaves become one

- [x] 2.1 Add the private `_interleave(arr, values)` helper to `sort.py` per design.md Decision 4 — a plain sync function taking the full array and the extracted values, returning the re-aligned column. Give it a docstring naming what it re-aligns and why the `None` elements were skipped. Verify `uv run ty check src` passes
- [x] 2.2 Rewrite `_column()` to extract `present` first, return `[None] * len(arr)` when it is empty, and route all three paths through `_interleave()`. Delete `trial_i`, the `next((i for i, element in enumerate(arr) ...), None)` scan and both `i != trial_i` comprehensions. Verify `uv run pytest tests/test_comparing.py tests/test_nulls_ordering.py` passes
- [x] 2.3 Verify the invocation-count claim in design.md Decision 4 directly, since it is what the rewrite rests on: instrument a counting extractor and assert the async path, the sync-that-lied path and the plain sync path each call it exactly once per non-`None` element — in particular that the lied path still calls the trial element's extractor once, not twice. Delete the instrumentation afterwards; this is a check, not a new test (proposal.md, Impact: no test changes)
- [x] 2.4 Update `_column()`'s docstring so its account of the one-time `isawaitable` safety net describes `results[0]` rather than "a trial call on the first non-`None` element ... i != trial_i", keeping the measured 1325ms-vs-9ms gather figure it already carries

## 3. `_sort_by_key()`: four `sorted()` sites become one

- [x] 3.1 Split the fan-out branch out on its own per design.md Decision 3: `len(segments) == 1` produces `columns = [await _segment_column(segments[0][0], arr)]`, everything else the existing `asyncio.gather(...)`. Apply `_tolerant_column()` and build `directions` once, below the branch, for both. Verify `uv run pytest tests/test_comparing.py` passes
- [x] 3.2 Replace the four lanes with the `(rows, reverse)` derivation from design.md Decision 1, followed by one `sorted(zip(rows, arr, strict=True), key=itemgetter(0), reverse=reverse)` and one `[element for _, element in paired]`. Add the `from operator import itemgetter` import. Verify `grep -c "sorted(zip" src/snakestream/sort.py` returns 1 and `uv run pytest tests/test_comparing.py tests/test_nulls_ordering.py tests/test_sorted.py` passes
- [x] 3.3 Verify the three preserved claims read off the shipped code rather than from a benchmark, per design.md Decision 1: the single-segment lane binds `rows` to the column itself with no `tuple(...)` on the path; the uniform lane reaches `sorted(..., reverse=True)` and not a reversal; the mixed lane wraps under `if d` per column
- [x] 3.4 Update `_sort_by_key()`'s docstring: its "A single ascending segment ... takes today's exact path: one column, no tuple build, no outer gather" sentence must name the lane and the fan-out branch rather than an early return that no longer exists (design.md, Risks). Every measured figure it carries stays

## 4. Gates

- [x] 4.1 Run `uv run pytest` and verify the pass count matches task 1.1 with no test file, test name or import changed — `git diff --stat tests/` must be empty (proposal.md, Impact)
- [x] 4.2 Run `uv run pytest --cov-fail-under=98` and verify it passes. Compare the per-file figure for `sort.py` against task 1.1 and **account for any drop rather than accepting it**: five branches are being removed, so a coverage change is expected, but an arm that became unreachable is a finding (design.md, Risks)
- [x] 4.3 Verify the stability gate specifically, since Decision 1 is what could break it: run `comparator-contract`'s stability scenarios plus `tests/test_comparing.py`'s all-descending, all-ascending and mixed-direction cases and `tests/test_nulls_ordering.py` in full, and confirm all pass unmodified (design.md Decision 5)
- [x] 4.4 Re-run the harness from task 1.2 against the **shipped** implementation and verify the -10% / -6% figures hold — the exploration measured the shapes in isolation, so this is what confirms them for the code actually landing. A result outside the measured direction means re-measuring interleaved before accepting it
- [x] 4.5 Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src` and `openspec validate collapse-sort-decorate-lanes --strict`, and verify all four pass. `ruff format` also covers Python fences in this change's own docs, so format the change directory before validating

## 5. Record the decisions

- [x] 5.1 Remove roadmap **Next** item 3 (`sort.py`'s `_column()` re-interleave) — this change closes it. Renumber the remaining two items and fix the cross-reference in item 1, which currently calls item 3 "warm-up for item 1". Verify by grepping `roadmap.md` for `_column` and for `re-interleave`: neither must survive outside **Done**
- [x] 5.2 Add a **Done** entry to `roadmap.md` carrying the three priced-and-declined alternatives so none is re-derived: the `(key, index)` no-`key=` decoration (5.71 ms, worse), `keys.__getitem__` over indices (a tie, no clearer), and folding the single-segment fan-out into `gather` (9.1 us against 192 ns, once per sort). **Done** is the rejection log, and these are exactly what it is for
- [x] 5.3 State in the **Done** entry that `comparator.py`'s segment-sign 2x2 — the remaining roadmap item in this neighbourhood — was deliberately left out and why (per-element path, +10% ns/element gate, would put a measured trade-off inside a gate-free change), so the next reader finds the sequencing rather than reading the omission as an oversight
- [x] 5.4 Verify no README migration-log entry is added, and state that absence in the commit message as a claim: nothing a caller can observe changed (proposal.md, Impact)
- [x] 5.5 Confirm `CLAUDE.md` needs no edit — it does not describe `sort.py`'s internals. Verify by grepping it for `sort` and checking every hit is about `sorted()` the operation or `Ordering.SET`, not about the module's structure
