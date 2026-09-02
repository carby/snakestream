## 1. Establish the baseline

- [x] 1.1 Record the current full-suite test count from `uv run pytest`; this exact number, with **zero test files edited**, is the acceptance gate at 5.1.
- [x] 1.2 Record the current coverage percentage and `terminals.py`/`stream.py` missed-statement counts from the default `addopts` run, so 5.2's dip can be attributed.
- [x] 1.3 Write the benchmark harness in a scratch directory (not in the repo): 20,000 elements, sync and async accumulators, the two variants interleaved round-robin, best of 3 across 10 rounds, three independent runs. Verify it reproduces design.md Decision 2's baseline column to within the stated noise before any code changes.

## 2. Collapse the sink

- [x] 2.1 In `stream.py`, replace `collect()`'s three-argument branch with a `Collector(supplier, accumulator, combiner)` construction driven through the same `_CollectorSink` path the single-argument branch uses; verify `uv run pytest tests/ -k "collect"` passes unedited.
- [x] 2.2 Carry the two surviving comments to the construction site: why the combiner is accepted and never invoked, and why this form cannot declare `Characteristics.UNORDERED` (design.md Decision 3). Verify neither comment still refers to a deleted name.
- [x] 2.3 Delete `Stream._collect_mutable()`, including its `await _maybe_await(supplier)`; verify `grep -n "_collect_mutable" src/` returns nothing.
- [x] 2.4 Delete `_MutableReductionSink` from `terminals.py`; verify `grep -rn "_MutableReductionSink" src/ tests/` returns nothing.
- [x] 2.5 Drop `terminals.py`'s `BiConsumer` import and `stream.py`'s `_maybe_await` import if nothing else in each file uses them; verify with `uv run ruff check .` (F401) rather than by eye.
- [x] 2.6 Add the `cast` at the combiner construction site only if `ty` asks for it (design.md Decision 5), with a comment naming the `BiConsumer[R,R]` / `Combiner[A]` mismatch and Java's identical one. Verify `uv run ty check src` is clean; do not add the cast preemptively.

## 3. Assert what the collapse must preserve

- [x] 3.1 Confirm `mutable-reduction-collect`'s "Empty stream still returns a container" scenario passes unedited — the supplier is still called once and its untouched container returned, with the accumulator never called.
- [x] 3.2 Confirm the supplier is called **exactly once** per `collect()` under both executors, with a counting supplier on a `.parallel()` stream as well as a sequential one; assert against the existing tests if they already cover it, and record here which test does rather than adding one.
- [x] 3.3 Confirm a raising supplier still raises before any element is pulled, out of the awaited `collect()` coroutine (design.md Decision 4). Record which existing test covers it, or that none does — an uncovered guarantee is a finding, not automatically a new test.
- [x] 3.4 Confirm `combiner` is still never invoked, sequential and parallel, via `mutable-reduction-collect`'s two existing scenarios.
- [x] 3.5 Confirm `test_callable_dispatch.py::test_collect_mutable_sync_call_returning_coroutine` passes unedited — the one-time `isawaitable` safety net still fires on `_CollectorSink`'s dispatch as it did on the deleted sink's.

## 4. Apply the gate

- [x] 4.1 Re-run 1.3's harness against the shipped code and record all six figures (two variants x three runs), baseline and collapsed.
- [x] 4.2 Apply the +10% ns/element threshold on the **sync** variant (design.md Decision 2). Over threshold → revert the whole change and record it in the roadmap **Done** entry as a measured rejection, the posture `collapse-terminal-collector-duplication` established. Record which branch was taken.

## 5. Verify the whole change

- [x] 5.1 `uv run pytest` full suite, with `git diff --stat tests/` empty; confirm the count matches 1.1.
- [x] 5.2 `uv run pytest --cov-fail-under=98`. If it fails, check whether a `_CollectorSink` branch became reachable from a second direction (design.md Risks) before adding any test.
- [x] 5.3 `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src`, `uv run --with pip-audit pip-audit`.
- [x] 5.4 Confirm `terminals.py`'s and `stream.py`'s remaining imports are all still used and that nothing in `src/` imports a deleted name.
- [x] 5.5 Confirm `git diff --stat README.md` is empty — no signature, return type, parity checkmark or migration entry changed, because nothing a caller can observe changed.

## 6. Documentation

- [x] 6.1 `CLAUDE.md`: check the Collectors section for any sentence made false by there being one collection sink; edit only if one is, and verify by re-reading the section rather than by grep.
- [x] 6.2 `roadmap.md`: add the **Done** entry carrying the full benchmark table from 4.1, the branch taken at 4.2, and the distinction that keeps this from licensing a re-collapse of the other sinks — counterpart versus no counterpart, box versus no box.
- [x] 6.3 `roadmap.md`: check whether **Next**'s "Claimed 2026-09-02" block still reads correctly once this change is Done — it names this change as deliberately absent from that list, which stays true, but its ranking rationale ("the only candidate whose per-element path is provably unchanged") should be verified against 4.2's outcome.
- [x] 6.4 State in the **Done** entry that no README migration entry exists and that the absence is a claim, per proposal.md — Impact.
