## 1. Establish the baseline

- [x] 1.1 Record the pre-change baseline: run `uv run pytest` and note the pass count and the `TOTAL` coverage percentage, so the gates in section 3 compare against a number rather than an impression (expected: 988 passed, 99%)
- [x] 1.2 Re-run the A/B harness from the exploration against **unmodified** `execution.py` to re-establish the baseline column on this machine, interleaved round-robin per design.md Decision 1, and verify the baseline figures land near 7.1-7.4 / 9.4-9.6 us/element; keep the script for task 3.4

## 2. The extraction

- [x] 2.1 Add the `@asynccontextmanager` helper to `execution.py`, placed beside `_maybe_aclosing()` per design.md Decision 2: it arms one `asyncio.create_task(anext(branch))` per branch into an `in_flight: dict[Task, int]`, yields that dict, and in its `finally` cancels every leftover task, `await asyncio.gather(..., return_exceptions=True)`s them, and `await branch.aclose()`s every branch. Verify by importing it and checking `uv run ty check src` passes
- [x] 2.2 Give the helper a docstring that states what the two callers share, why the `finally` is load-bearing on an early exit, and that closing the branches applies to both paths (design.md Decision 3) — matching the density of the docstrings already in this module. Verify `uv run ruff check .` and `uv run ruff format --check .` pass
- [x] 2.3 Convert `_release_in_order()` to enter the helper, deleting its own arm line and its five-line `finally` while keeping its `pending`/`trailing` buffer, its `index is None` branch, its `_releasable()` drain and its trailing flush unchanged. Verify `uv run pytest tests/test_racing_encounter_order.py tests/test_racing_delivery_order.py` passes, including the direct `_release_in_order(branches, window)` call at `tests/test_racing_encounter_order.py:669`
- [x] 2.4 Convert `race_through()`'s no-split path to enter the helper, deleting its arm line and its `finally` and keeping the `while`/`for` body and its bare `yield result`. This is where branch-closing becomes new behaviour on that path (design.md Decision 3). Verify `uv run pytest tests/test_parallel.py tests/test_find_any.py tests/test_execution_model.py` passes
- [x] 2.5 Update `execution.py`'s module docstring with a clause naming the shared branch-task lifecycle, without promoting the helper to a fifth primitive in the four-primitive list (proposal.md, Impact). Verify the four named primitives are still exactly `stream_through`, `race_through`, `feed_through`, `drain`

## 3. Gates

- [x] 3.1 Run `uv run pytest` and verify the pass count matches task 1.1 with no test file, test name or import changed — `git diff --stat tests/` must be empty (proposal.md, Impact)
- [x] 3.2 Run `uv run pytest --cov-fail-under=98` and verify the gate passes. Removing two `finally` blocks changes the branch count, so compare the per-file figure for `execution.py` against task 1.1 and account for any drop rather than accepting it — an arm that became unreachable is a finding, as it was in `sort-with-cmp-to-key`
- [x] 3.3 Verify the close-count requirements specifically, since task 2.4 changes that path: run the `racing-encounter-order` scenarios asserting barrier and no-barrier close counts are equal, plus `stream-execution-model`'s "closeable source is still closed under racing" and "racing over an async iterator with no `aclose()`", and confirm all pass unmodified
- [x] 3.4 Re-run the harness from task 1.2 against the **shipped** implementation and verify it is within noise of the baseline column — the exploration measured a scratchpad reimplementation, so this is what confirms the zero-cost claim for the code actually landing. A result outside +/-1% means re-measuring interleaved before accepting it
- [x] 3.5 Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src` and `openspec validate extract-racing-task-lifecycle --strict`, and verify all four pass

## 4. Record the decision

- [x] 4.1 Add a **Done** entry to `roadmap.md` recording that variant A was measured and declined, carrying the figures table, the harness, and the interleaving caveat from design.md Decision 1 — **Done** is the rejection log, so a future reader must find A priced there rather than re-derive it (design.md, Risks)
- [x] 4.2 Verify no README migration-log entry is added, and state that absence in the commit message as a claim: nothing a caller can observe changed (proposal.md, Impact)
- [x] 4.3 Confirm `CLAUDE.md` needs no edit — its architecture section lists the execution primitives and the helper is not one. Verify by re-reading that section against the shipped `execution.py`
