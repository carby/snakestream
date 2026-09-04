## 1. Add the free-threaded leg

- [x] 1.1 In `.github/workflows/check.yml`, add the free-threaded build to the `code_check` matrix alongside `3.14`; verify the identifier `astral-sh/setup-uv` accepts resolves to a free-threaded interpreter, and confirm in the first CI run's log that `sys._is_gil_enabled()` is `False` on that leg rather than assuming the spelling worked (design: Risks).
- [x] 1.2 Leave the `install_smoke_test` matrix at its single `3.14` leg (design decision 1). Verify the premise rather than trusting it: `uv build --wheel` produces a `py3-none-any` wheel and `project.dependencies` is empty, so a second leg would install a byte-identical artifact. Record both checks.
- [x] 1.3 Verify `code_check` still runs lint, format check and the test suite on **every** leg.

## 2. Restore the per-leg gating

- [x] 2.1 Re-add `if:` conditionals to the `ty`, `pip-audit` and coverage-threshold steps, gating each on the GIL-enabled `3.14` leg; verify each carries a comment stating the reason (the check does not vary by interpreter build) rather than restating the condition.
- [x] 2.2 Verify the coverage gate passes on the GIL leg at the existing `--cov-fail-under=98` with no threshold change. Record the figure.
- [x] 2.3 Confirm the coverage figures are identical on both builds by running the gate in a clean free-threaded virtualenv — expected 1512 statements, 2 missed, 99% (design decision 2). This is a one-time confirmation of the corrected measurement, not a CI step.

## 3. Verify the library on the free-threaded build

- [x] 3.1 Create a clean free-threaded environment (`uv venv --python 3.14t`, then `uv pip install -e .` plus pytest, pytest-asyncio, pytest-mock, pytest-cov, hypothesis) and run the full suite; verify 1000 tests pass with no skips, xfails or build-conditional branches (design decision 3).
- [x] 3.2 Verify no `sys._is_gil_enabled()` or equivalent build check was added anywhere in `src/` or `tests/`; `grep` for it and confirm zero hits.

## 4. Record the audit as requirements

- [x] 4.1 Verify the `free-threaded-support` delta's three requirements match what the tree actually holds: no module-level mutable state, `ClassVar`s immutable only, per-composition dispatch state. Re-run each check rather than trusting the proposal's summary.
- [x] 4.2 Confirm no `install-smoke-test` delta exists in this change and that `openspec/specs/install-smoke-test/spec.md` is untouched; confirm with `openspec validate add-free-threaded-ci-leg`.
- [x] 4.3 Record in the change (not in `src/`) the forward obligation for change 2: `execution.py`'s two `asyncio.Lock` sites guard the shared-source pull and are not thread-safe across event loops. Verify the count is still exactly two at implementation time — if it has changed, the obligation changes with it.

## 5. Update the prose

- [x] 5.1 In `CLAUDE.md`, update the CI description to name both legs and state which checks run on which; verify it no longer describes a single-leg matrix.
- [x] 5.2 Add a `CLAUDE.md` command line for running the suite on a free-threaded build locally, so a contributor can reproduce the leg without reading the workflow.
- [x] 5.3 Verify no README Migration entry is needed — nothing observable to a caller changes. Record that judgment rather than leaving the absence unexplained.

## 6. Validate as CI does

- [x] 6.1 Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`, `uv run ty check src` and `uv run pytest --cov-fail-under=98` on the GIL build; verify all pass.
- [x] 6.2 Run the lint, format and test steps in the free-threaded environment; verify all pass.
- [x] 6.3 Run `openspec validate add-free-threaded-ci-leg`; verify it reports valid.
- [x] 6.4 Confirm `git diff --stat` touches no file under `src/`.
