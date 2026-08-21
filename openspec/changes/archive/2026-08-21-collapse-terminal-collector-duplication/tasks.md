## 1. Establish the baseline and the benchmark harness

- [x] 1.1 Confirm the starting state is clean and green: `uv run pytest` (505 tests) and `uv run pytest --cov-fail-under=98`. Record the test count and coverage figure — they are the numbers every later step is compared against.
- [x] 1.2 Write the benchmark script to the scratchpad (not the repo) following design.md Decision 3: 20,000 elements, **no intermediate chain**, best of 5, interleaved reps in one process, three independent process invocations per variant, on Python 3.14.5. Cover six variants: `count()`, `min(comparator)` sync, `min(comparator)` async, `reduce(accumulator)` sync, `reduce(identity, accumulator)` sync, `reduce(accumulator)` async.
- [x] 1.3 Run it against unmodified `HEAD` and record the baseline ns/element for all six. Sanity-check the spread across the three invocations is in the ~10% range past records show; if it is much wider, fix the harness before trusting any comparison.

## 2. Audit each pair for behavioural drift before deleting anything

- [x] 2.1 Diff `_MinMaxSink.accept`/`_finish` against `_extremum`'s `_accumulate`/`_finish` line by line. Confirm the only differences are where the dispatch state lives (`self` vs. `_ExtremumBox`). Note any other delta — it is a bug in one of them, not a refactor detail.
- [x] 2.2 Same for `_CountSink` vs. `counting()`.
- [x] 2.3 Same for `_ReduceSink` vs. `reducing()`'s no-mapper form, specifically checking the `AsyncDispatch` vs. `_classify_step` spelling (design.md Risks) and that `reduce(identity, acc)` over an empty source returns `identity` on both sides while `reduce(acc)` returns `None`.
- [x] 2.4 If any audit turns up a real difference, stop and report it before continuing — it changes the scope from refactor to fix.

## 3. Collapse `count()`

- [x] 3.1 Rewrite `Stream.count()` as `return await self.collect(counting())`; import `counting` in `stream.py`.
- [x] 3.2 Delete `_CountSink` from `terminals.py` and drop the now-unused `Counter` import there.
- [x] 3.3 `uv run pytest` — every test passes with **no test file edited**. If a test needs editing, treat it as a behaviour change and stop.
- [x] 3.4 Benchmark the `count()` variant and compare against the 1.3 baseline. Record the three-run figures.
- [x] 3.5 Apply the gate: within +10% → keep the collapse. Over → revert this group and take design.md Decision 4's `count` fallback (leave `_CountSink`, swap its `Counter` box for a plain `int`). Record which branch was taken and why.

## 4. Collapse `min()` / `max()`

- [x] 4.1 Rewrite `Stream._min_max()` to `collect(min_by(comparator))` / `collect(max_by(comparator))`; import both in `stream.py`.
- [x] 4.2 Delete `_MinMaxSink` from `terminals.py`, dropping the `Comparator` and `check_comparator_result_type` imports if nothing else there uses them.
- [x] 4.3 `uv run pytest` — passes unedited, including the comparator-contract tests that assert a `bool`-returning comparator raises `TypeError` from `min()`/`max()`.
- [x] 4.4 Benchmark the sync and async `min` variants; record the figures.
- [x] 4.5 Apply the gate on the **sync** variant (design.md Decision 3). Over threshold → revert this group and take the Decision 4 fallback: extract the sync compare-and-keep helper (sign check, `asc` test, first-of-tied rule, contract comment) called from both `_MinMaxSink.accept` and `_extremum._accumulate`. Record which branch was taken.

## 5. Collapse `reduce()`

- [x] 5.1 Rewrite `Stream.reduce()` to call `reducing(accumulator)` when `identity is _UNSET` and `reducing(identity, accumulator)` otherwise (design.md Decision 2); import `reducing` in `stream.py`.
- [x] 5.2 Delete `_ReduceSink` from `terminals.py` and drop the now-unused `Accumulator` import if nothing else there uses it.
- [x] 5.3 `uv run pytest` — passes unedited, including both `reduce()` overloads, the empty-source cases and the async-accumulator cases.
- [x] 5.4 Benchmark all three `reduce` variants; record the figures. The sync no-identity variant is the one carrying `reducing`'s extra `mapper is not None` branch.
- [x] 5.5 Apply the gate. Over threshold → revert this group and take the Decision 4 `reduce` fallback (keep `_ReduceSink`; cross-reference the two bodies as one documented rule). Record which branch was taken.
- [x] 5.6 Answer design.md's open question in a sentence: whether `Counter` still has a user besides `counting()` after whatever landed.

## 6. Verify the whole change

- [x] 6.1 `uv run pytest` full suite, still with zero test files edited; confirm the count matches 1.1.
- [x] 6.2 `uv run pytest --cov-fail-under=98`. If it fails, check whether a `reducing()` branch became reachable only from one direction (design.md Risks) before adding any test.
- [x] 6.3 `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src`. Note any `cast` `ty` forced at a `collect()` call site rather than adding one preemptively.
- [x] 6.4 Confirm `terminals.py`'s remaining imports are all still used and that `stream.py` no longer imports any deleted sink.

## 7. Documentation

- [x] 7.1 README: invert the layering sentence in the `min_by` / `max_by` rows ("Wraps `Stream.min()`'s existing logic") and the `reducing` row ("Mirrors `Stream.reduce()`'s existing semantics") for whichever terminals collapsed. No checkmark, signature or return-type edit — verify none changed.
- [x] 7.2 `roadmap.md`: move item 1 from **Now** to **Done**, carrying the full benchmark table (all six variants, three runs each, baseline vs. collapsed) and, per terminal, whether it collapsed or took the fallback and why.
- [x] 7.3 `roadmap.md`: strike part (c) from item 3's small-cleanups batch — resolved if `count` collapsed, folded into task 3.5's fallback if it did not — and renumber or renote the batch accordingly.
- [x] 7.4 If any terminal took the fallback, state in the **Done** entry that the collapse is now a measured, deliberately-rejected trade rather than an open cleanup — the same posture `add-callsite-dispatch` established — so it is not re-proposed without new evidence.
