## 1. Pin the baseline

- [ ] 1.1 Copy `src/snakestream/comparator.py` to a scratch `comp_baseline.py` and a byte-identical `comp_null.py`, outside the project tree. Verify `cmp comp_baseline.py comp_null.py` reports no difference — every later correctness and performance claim is against this pair.
- [ ] 1.2 Reproduce the pre-change figures with `bench_specialize.py` against baseline/null only, and verify the null test separates by under ~1% on the sync and cheap-async shapes. A larger floor means the machine is too noisy to judge this change on; fix that before continuing.

## 2. Build the two builders

- [ ] 2.1 Add `_build_extract(extractor, nulls, is_async) -> Any` returning the `(a, b) -> (ea, eb)` half: a bare-segment form (`extractor is None`, never async), plus keyed sync/async and keyed-tolerant sync/async forms. Give each closure a real name so tracebacks identify the shape. Verify by unit-calling all five forms directly, including that the bare form returns `(a, b)` unchanged and that no tolerant form is constructed when `nulls is NullPlacement.ABSENT`.
- [ ] 2.2 Add `_build_compare(comparator, nulls) -> Any` returning the `(ea, eb) -> sign` half in four forms — natural, checked, tolerant-natural, tolerant-checked — with `comparator is None` selecting natural ordering and returning **before** the `type(sign) is not int` guard, per design.md Decision 2. Verify a checked form raises `ComparatorContractException` on a non-`int` and a tolerant form returns `_null_sign`'s answer for a `None` side and `0` for a both-`None` pair.
- [ ] 2.3 Resolve `C901 _build_compare is too complex (11 > 10)` (design.md Risks) by splitting the tolerant leaves into their own builder or lifting the four leaves to module scope. Verify `uv run ruff check src` passes.

## 3. Rewire KeyComparator

- [ ] 3.1 Replace `self._norm` with `self._plan` in `KeyComparator.__init__` — per segment an `(extract, compare, descending, is_async)` tuple built by the two builders. Leave `self.segments`, `self.nulls` and `self._any_async` untouched. Verify `uv run pytest tests/test_sorted.py` still passes, since `sort.py` reads `.segments`.
- [ ] 3.2 Rewrite `_compare_sync` as `extract` / `compare` / negate / short-circuit with no reference to `self.nulls`, and `_compare_async` the same with `await extract(a, b) if is_async else extract(a, b)` (design.md Decision 2 — never wrap a sync extractor in a coroutine). Verify `uv run pytest tests/test_comparator.py tests/test_min_max.py` passes.
- [ ] 3.3 Delete `_extract_pair_sync`, `_extract_pair_async`, `_segment_sign_sync` and `_segment_sign_async`. Verify `grep -n "_segment_sign\|_extract_pair\|_norm" src/ tests/` returns nothing outside docstrings you have already rewritten.

## 4. Prove behaviour is unchanged

- [ ] 4.1 Run the 26-shape × 49-pair equivalence harness (benchmark-findings.md, Correctness) comparing sign *and* raised exception type against `comp_baseline.py`. Verify zero mismatches. This is the acceptance bar; the unit suite alone does not cover several of these shapes.
- [ ] 4.2 Add regression tests for the two load-bearing null behaviours named in design.md Context: that `comparing(f)` with `NullPlacement.ABSENT` raises out of the extractor on a `None` element rather than sorting it last, and that a tolerant chain with a `then_comparing(comparator)` bare-comparator tie-break still tolerates null elements. Verify both fail against a deliberately broken builder before passing against the real one.
- [ ] 4.3 Run the full suite: `uv run pytest`. Verify it passes and coverage holds at the CI gate (`uv run pytest --cov-fail-under=98`).

## 5. Measure and record

- [ ] 5.1 Re-run `bench_specialize.py` with `comp_plan.py` taken from the implemented file, and verify every shape is negative against baseline and outside the null floor. If any shape regresses, stop and report rather than adjusting the harness.
- [ ] 5.2 Re-run the construction benchmark and verify the cost stays in the range design.md Decision 4 accepts (+10% to ~+50%, break-even ~11 sync comparisons). A materially larger construction cost invalidates Decision 4 and needs re-deciding, not absorbing.
- [ ] 5.3 Update `benchmark-findings.md` with the as-implemented figures, marking clearly which table is the prototype's and which is the shipped shape's — the archived `merge-segment-sign-on-natural-ordering` entry records a peer review catching prototype figures left standing as fact after the shape changed.

## 6. Documentation and close-out

- [ ] 6.1 Rewrite the `KeyComparator` class docstring: it currently describes `_norm` as "a derived view only `__call__` reads" and cites `merge-segment-sign-on-natural-ordering` Decision 1/4. Verify no docstring in `comparator.py` still names a deleted function.
- [ ] 6.2 Update CLAUDE.md if it names any of the deleted helpers. Verify `grep -n "_segment_sign\|_extract_pair\|_norm" CLAUDE.md README.md` returns nothing stale. No README Migration entry is owed — no public API or behaviour changes (proposal.md, What Changes).
- [ ] 6.3 Close `roadmap/items/segment-sign-sharing-cost.md`: move its prose to `roadmap/decisions.md` as a new top entry recording that the tail question was answered by side effect — the tail became shareable, not singular, and the change that did it was justified on performance (design.md Decision 3). Delete the item file, run `python tools/roadmap_index.py`, and verify `uv run pytest tests/test_roadmap.py` passes.
- [ ] 6.4 Run `uv run ruff check .`, `uv run ruff format --check .` and `uv run ty check src`. Verify all three pass, and run `uv run --python 3.14t pytest` for the free-threaded CI leg.
