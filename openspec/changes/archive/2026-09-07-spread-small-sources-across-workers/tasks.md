## 1. Confirm the sequencing precondition

- [x] 1.1 Confirm `ramp-batch-growth-geometrically` has landed — `openspec/changes/archive/2026-09-07-ramp-batch-growth-geometrically/` exists and `src/snakestream/execution.py` grows batch size by `min(size * 8, BATCH_SIZE)` from a per-worker seed of 1, with no `_FIRST_BATCH_SIZE` left in the module. If either is false, stop: this change is inert without it (design.md, Migration Plan).

## 2. Verify the guarantee

- [x] 2.1 Add a test to `tests/test_fork_join.py` asserting that a 200-element source under `.parallel()` runs batches on more than one distinct worker thread, and that the collected result equals the `.sequential()` result — collecting `threading.current_thread()` inside the mapper, the pattern already used at `tests/test_fork_join.py:296`, never a wall-clock assertion (design.md decision 3). Verify with `uv run pytest tests/test_fork_join.py`.
- [x] 2.2 Add a test that a source exhausted before batch size reaches `BATCH_SIZE`, but with more than `WORKERS` elements, still reaches more than one worker — the "distribution does not wait for the ramp to climb" requirement. Verify with `uv run pytest tests/test_fork_join.py`.
- [x] 2.3 Confirm the new tests actually catch the old behaviour: monkeypatch the growth step to jump straight to `BATCH_SIZE` after the first round (the pre-ramp curve), observe the assertions in 2.1 and 2.2 fail, then revert the patch — the deliberate-break discipline from task 4.3 of `fork-join-executor-and-spliterator`. Record the observed failure in the commit message or in `benchmark-findings.md`; do not leave the patch in the tree.
  - Finding (recorded, design.md decision 3 revised accordingly): monkeypatching the true pre-ramp shape (seed 4, then jump straight to `BATCH_SIZE`) did **not** make either assertion fail. Round one alone already dispatches up to `WORKERS` concurrent batches regardless of seed size, so both old and new code touch more than one thread for any source bigger than `WORKERS`. The pre-ramp cliff was a work-concentration problem (most elements landing in one worker's round-two batch), not a "only one thread ever runs" problem — the thread-count test correctly verifies the stated (deliberately weak) requirement but does not double as a regression guard for the cliff itself. Patch was reverted; `git diff --stat src/snakestream/execution.py` confirms no residue.
- [x] 2.4 Confirm no test asserts a source of `WORKERS` elements or fewer reaches more than one worker — that case is deliberately unspecified (spec, second scenario of the first requirement).

## 3. Measure

- [x] 3.1 Write a throwaway benchmark (scratchpad, not committed to `tests/`) comparing a CPU-bound mapping pipeline under `.parallel()` against `.sequential()` at n=200 and n=800, run under `uv run --python 3.14t`, and record the ratios.
- [x] 3.2 Run the same benchmark on the GIL-enabled build (`uv run`) and record those ratios too, so the README claim can be stated per-build rather than unqualified.
- [x] 3.3 Write `openspec/changes/spread-small-sources-across-workers/benchmark-findings.md` carrying both builds' figures with their source sizes, the interpreter versions, and the benchmark source — the roadmap convention that a performance claim carries its measurement. Verify the file exists and its numbers are the ones the README edits in section 4 will quote.

## 4. Retract the caveat

- [x] 4.1 Edit README's "About `.parallel()`" (README.md:68): delete the sentence beginning "That last qualifier matters:" and state the measured small-source behaviour from 3.3 in its place. Verify by grepping README for "spans enough batches" and finding nothing.
- [x] 4.2 Edit README's 0.3.5 Migration entry (README.md:284): delete the parenthetical "with enough elements to spread across more than one worker's batch", leaving the rest of the cheap-callable regression entry intact (design.md decision 4). Verify by grepping for "spread across more than one worker" and finding nothing.
- [x] 4.3 Edit `CLAUDE.md`'s "Sequential vs. parallel execution": delete "but only once the source spans enough batches to spread across workers — a small source can land entirely in one worker's batch and see no benefit" and state distribution as the guarantee instead. Verify by grepping `CLAUDE.md` for "land entirely in one worker's batch" and finding nothing.
- [x] 4.4 Add a `Stream` table note or README pointer to the new `parallel-worker-utilisation` capability wherever README already points at `racing-encounter-order` and `parallel-reduction` for parallel behaviour, so the guarantee is discoverable from the docs that used to carry the caveat.

## 5. Gates and close-out

- [x] 5.1 Run `uv run ruff check .`, `uv run ruff format --check .`, and `uv run ty check src` — all clean.
- [x] 5.2 Run `uv run pytest --cov-fail-under=98` on the GIL-enabled build and `uv run --python 3.14t pytest` on the free-threaded build; both green, matching what CI runs on each leg.
- [x] 5.3 Run `openspec validate spread-small-sources-across-workers --strict` and confirm it passes with all four artifacts present.
- [x] 5.4 Close the roadmap item: move `roadmap/items/spread-small-sources-across-workers.md`'s prose to the top of `roadmap/decisions.md` as a new entry (recording the measured figures and that the change shipped no mechanism of its own), delete the item file, and run `python tools/roadmap_index.py`. Verify with `uv run pytest tests/test_roadmap.py`.
