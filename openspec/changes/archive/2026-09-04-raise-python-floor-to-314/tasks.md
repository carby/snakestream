## 1. Move the floor

- [x] 1.1 In `pyproject.toml`, set `requires-python = ">=3.14"`; verify `uv sync` resolves and `uv run python -c "import snakestream"` succeeds.
- [x] 1.2 In `pyproject.toml`, set `[tool.ruff] target-version = "py314"`; verify `uv run ruff check .` reports exactly 17 `UP037` findings and nothing else.
- [x] 1.3 In `.readthedocs.yml`, raise `python: version:` from `"3.13"` to `"3.14"`; verify no pin in the repo now sits below `requires-python`. Do **not** address the missing `docs/` directory (design decision 4) — confirm it is reported in `proposal.md`'s Impact and leave it.

## 2. Unquote the annotations

- [x] 2.1 Run `uv run ruff check --select=UP037 --fix .` — scoped to the one rule, not a bare `--fix`. Verify the diff is exactly 17 edits: 13 in `src/snakestream/comparator.py` and 4 across `tests/test_execution_model.py`, `tests/test_racing_delivery_order.py`, `tests/test_racing_encounter_order.py`, each removing only quotes.
- [x] 2.2 **Import-time check, not just a type check.** `comparator.py` has no `from __future__ import annotations`, so its unquoted annotations now depend on PEP 649's deferred evaluation, and several reference `KeyComparator` before it is defined in the file (design decision 1). Verify with `uv run python -c "import snakestream.comparator"` and by running `uv run pytest tests/test_comparing.py tests/test_comparator_segments.py tests/test_nulls_ordering.py tests/test_max_by.py tests/test_min_by.py` — a `NameError` here is the failure mode `ty` would not catch.
- [x] 2.3 Verify `uv run ruff check .` is clean — zero findings, not merely no `UP037`.
- [x] 2.4 Confirm the nine `src/` modules and one test carrying `from __future__ import annotations` are untouched (design decision 3); verify the count is unchanged with `grep -rc "from __future__ import annotations" src/ tests/`.

## 3. Collapse the CI matrix

- [x] 3.1 In `.github/workflows/check.yml`, set both matrices to `["3.14"]`; verify by grep that no `3.13` remains in the file.
- [x] 3.2 Remove the three `if: matrix.python-version == '3.14'` conditionals from the `ty`, `pip-audit` and coverage-threshold steps, along with the comments justifying each restriction — those comments describe a redundancy across interpreters that no longer exists (design decision 2). Keep the steps themselves.
- [x] 3.3 Verify no step was disabled rather than unconditioned: read the workflow and confirm `code_check` still runs all five of lint, test, `ty`, `pip-audit` and the coverage gate, now unconditionally. Confirm again against the actual step list of the first CI run after the commit rather than assuming.
- [x] 3.4 Confirm the matrix is **kept** at one element rather than removed, so a later free-threaded leg is a matrix edit and not a restructure (design decision 2).

## 4. Update the spec

- [x] 4.1 Verify the `install-smoke-test` delta states both the current one-leg matrix and the reason the job stays matrix-shaped; confirm with `openspec validate raise-python-floor-to-314`. (Archive applies it — do not hand-edit `openspec/specs/`.)
- [x] 4.2 Re-read `openspec/specs/static-type-checking/spec.md` ("at least one Python version in the build matrix") and `openspec/specs/lint-rule-selection/spec.md` ("every matrix leg") against the one-leg matrix; verify both remain literally true and record that no delta is needed.

## 5. Correct the prose

- [x] 5.1 In `CLAUDE.md`, change "across Python 3.13–3.14" to name 3.14 alone, and update the trailing clause about `ty`/`pip-audit`/coverage running "only on the 3.14 leg" — with one leg that distinction is gone. Verify no `3.13` remains in the file.
- [x] 5.2 Add a README Migration entry for the dropped interpreter, noting as the 3.13 entry did that there is **no** silent break in this step. Since this is the last of four, state the resulting floor plainly (3.14 only) so a reader arriving at any one entry can find the endpoint. Cite `openspec/changes/raise-python-floor-to-314`.
- [x] 5.3 Grep the repo for remaining `3.13` claims outside `openspec/changes/archive/`; verify every surviving hit is historical narrative or deliberately out of scope, and record which.
- [x] 5.4 Verify README's `## Migration` section now carries all four floor-raise entries and that they read coherently in sequence — the 3.12 entry's introspection break is the only silent one, and a reader upgrading straight from 3.10 should be able to tell that from the entries alone.

## 6. Validate as CI does

- [x] 6.1 Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`, `uv run ty check src` and `uv run pytest --cov-fail-under=98`; verify all pass. Record the coverage figure before and after — unchanged is expected, since no branch is added or removed.
- [x] 6.2 Run `openspec validate raise-python-floor-to-314`; verify it reports valid.
- [x] 6.3 Confirm the change took **nothing** beyond the bump: no `spliterator()`, no free-threaded matrix leg, no `execution.py` edit. Verify `git diff --stat` touches only `pyproject.toml`, `.github/workflows/check.yml`, `.readthedocs.yml`, `src/snakestream/comparator.py`, three test files, `CLAUDE.md`, `README.md` and the change's own artifacts.
