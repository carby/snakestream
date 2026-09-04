## 1. Move the floor

- [x] 1.1 In `pyproject.toml`, set `requires-python = ">=3.11"`; verify `uv sync` still resolves and `uv run python -c "import snakestream"` succeeds.
- [x] 1.2 In `pyproject.toml`, set `[tool.ruff] target-version = "py311"`; verify `uv run ruff check .` now reports exactly two findings — `UP036` at `stream.py:353` and `RUF100` at `stream.py:345` — and nothing else.
- [x] 1.3 In `.github/workflows/check.yml`, drop `"3.10"` from both matrices (`code_check` and `install_smoke_test`), leaving 3.11–3.14; verify by grep that no `3.10` remains in the file and that the `if: matrix.python-version == '3.14'` conditionals are untouched.

## 2. Delete what the floor unlocks

- [x] 2.1 In `src/snakestream/stream.py`, delete the `if sys.version_info >= (3, 11):` guard in `close()` and dedent the `add_note()` loop so it runs unconditionally; verify `uv run ruff check .` no longer reports `UP036`.
- [x] 2.2 In the same method, delete the `# noqa: PERF203` directive and reword the comment above it to state `close()`'s every-handler contract on its own terms, without reference to the rule (design decision 4); verify `uv run ruff check .` no longer reports `RUF100` and reports nothing at all.
- [x] 2.3 Remove `import sys` from `src/snakestream/stream.py`, now unused; verify with `grep -n "sys\." src/snakestream/stream.py` returning nothing and `uv run ruff check .` staying clean.
- [x] 2.4 In `tests/test_close.py`, remove the `@pytest.mark.skipif(sys.version_info < (3, 11), ...)` marker from `test_close_with_three_raising_handlers_notes_the_other_two`, and remove `import sys` if it has no other use; verify `uv run pytest tests/test_close.py` passes with that test running rather than skipped.
- [x] 2.5 Add a test asserting note attachment is unconditional, covering the new spec scenario "Note attachment is not conditioned on the interpreter" — two raising handlers, first raised carrying one note — and verify it passes. If the existing three-handler test already covers the scenario adequately, record that judgment here instead of adding a redundant test.
  - Judgment: no new test added. `test_close_with_three_raising_handlers_notes_the_other_two` (task 2.4) previously skipped on <3.11 and now runs unconditionally on every supported interpreter, directly asserting notes are attached for the later exceptions. That is exactly the "not conditioned on the interpreter" scenario — three handlers rather than two, but no separate no-notes code path exists to distinguish. A two-handler variant would be redundant.

## 3. Restate the specs

- [x] 3.1 Apply the `stream-close-handling` delta to `openspec/specs/stream-close-handling/spec.md`: replace the single `close() invokes every registered close handler` requirement with the two requirements from `specs/stream-close-handling/spec.md`, preserving the `ExceptionGroup` paragraph's Java reasoning verbatim apart from its reworded closing clause; verify `openspec validate raise-python-floor-to-311` passes. (Archive performs this — do not hand-edit the main spec during apply.)
  - Not hand-edited, per instruction. `openspec validate raise-python-floor-to-311` reports valid.
- [x] 3.2 Confirm the `install-smoke-test` delta covers every 3.10 mention in `openspec/specs/install-smoke-test/spec.md` — the Purpose sentence included, which the delta does not touch since Purpose is not a requirement; if the Purpose names a version range, note that it needs a direct edit at archive time and record it here.
  - Checked: the main spec's Purpose sentence (line 3) says "the full supported Python matrix" — it does not name a version range, so no direct edit is needed at archive time. The two 3.10 mentions in the file are both inside the `close() runs...` requirement/scenario at lines 8 and 12, which the delta fully replaces.

## 4. Correct the prose

- [x] 4.1 In `CLAUDE.md`, change "across Python 3.10–3.14" to "across Python 3.11–3.14"; verify by grep that no `3.10` remains in the file.
- [x] 4.2 In `roadmap.md`, amend the `ExceptionGroup` decision entry (~line 1103) so the "expiry date … 3.10 leaves the matrix in October 2026" prediction reads as fact rather than forecast, naming this change; verify the surrounding claim — that the decision never rested on that objection — is left intact.
- [x] 4.3 Add a README Migration entry under `## Migration` for the dropped interpreter: what breaks (install on 3.10), how loudly (`pip` resolution error, not a runtime failure), what does not change (behaviour on every supported interpreter, `close()` included), and why (the four-step floor raise and its destination). Verify it matches the density and shape of the surrounding entries and cites `openspec/changes/raise-python-floor-to-311`.
- [x] 4.4 Grep the whole repo for remaining `3.10` claims outside `openspec/changes/archive/` (archived changes are history and are not rewritten); verify every surviving hit is either historical narrative or deliberately out of scope, and record which.
  - Main specs (`openspec/specs/stream-close-handling/spec.md`, `openspec/specs/install-smoke-test/spec.md`): still mention 3.10 — expected, handled by archive per 3.1/3.2, not hand-edited during apply.
  - `roadmap.md:2291,3665,4152`: historical narrative about past decisions/changes; correctly left as-is.
  - This change's own artifacts (`proposal.md`, `design.md`, `tasks.md`, delta specs): describe 3.10 as the thing being dropped; expected.
  - **Gap found and fixed (out of the proposal's stated Impact, surfaced and confirmed with the user):** `.github/workflows/deliver.yml:24`, the merge-triggered release workflow, had its own `python-version` matrix including `"3.10"`, unmentioned anywhere in the planning artifacts. Left alone it would run `uv sync`/`pytest` against 3.10 and fail once `requires-python` moved to `>=3.11`. Dropped `3.10` from that matrix too, matching the `check.yml` edit.

## 5. Validate as CI does

- [x] 5.1 Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`, `uv run ty check src` and `uv run pytest --cov-fail-under=98`; verify all pass, matching what CI runs on the 3.14 leg. Record the coverage figure before and after, confirming the deleted branch did not lower it (design: Risks).
  - All five pass: ruff check clean, ruff format clean (600 files), pytest 1000 passed, ty check src clean, cov-fail-under=98 gate passes.
  - Coverage before (stashed, pre-change): 98.61%. Coverage after: 98.66%. Rose, not lowered — consistent with removing a statically-true branch.
- [x] 5.2 Run `openspec validate raise-python-floor-to-311`; verify it reports valid.
  - `openspec validate raise-python-floor-to-311` reports: Change 'raise-python-floor-to-311' is valid
