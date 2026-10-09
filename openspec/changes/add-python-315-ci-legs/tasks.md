## 1. Add the 3.15 legs to `code_check`

- [x] 1.1 In `.github/workflows/check.yml`, set the `code_check` matrix to `["3.14", "3.14t", "3.15", "3.15t"]`; verify by reading the file back that lint, format check and the test suite carry no `if:` and so run on every leg.
- [x] 1.2 Move the `ty`, `pip-audit` and coverage-threshold guards from `'3.14'` to `'3.15'` (design decision 1), and reword the comment above them to say they run once, on the newest GIL-enabled leg, rather than naming a version; verify exactly three guards exist and all read `'3.15'`.
- [x] 1.3 Run the suite locally on both new builds: `uv run --python 3.15 pytest --cov-fail-under=98` and `uv run --python 3.15t pytest`. Verify both pass with no skips or xfails beyond those on 3.14, and record the interpreter version actually used (rc or final) and the coverage figure.
- [x] 1.4 Run `uv run --python 3.15 ruff check .`, `uv run --python 3.15 ruff format --check .`, `uv run --python 3.15 ty check src` and `uv run --python 3.15 --with pip-audit pip-audit`, and verify all pass.
- [x] 1.5 Grep `src/` and `tests/` for `sys.version_info` and `_is_gil_enabled` and verify this change adds no hits (design decision 4).

## 2. Cover 3.15 in the packaging checks

- [x] 2.1 Set the `install_smoke_test` matrix to `["3.14", "3.15"]`, then re-verify design decision 2's premises: `uv build --wheel` yields a `py3-none-any` wheel and `project.dependencies` is empty. Record both.
- [x] 2.2 Reproduce the smoke-test path locally on 3.15: create a seeded venv in the scratchpad, `pip install .`, and `python -c "import snakestream"` from outside the repo. Verify the import succeeds.
- [x] 2.3 In `.github/workflows/deliver.yml`, set the matrix to `["3.14", "3.15"]` and move its `pip-audit` guard to `'3.15'` (design decision 3); verify by reading the file back.

## 3. Update the prose

- [x] 3.1 In `CLAUDE.md`, rewrite the CI paragraph for four `code_check` legs, the single-leg checks on the newest GIL-enabled leg, and a two-leg `install_smoke_test`; add a `uv run --python 3.15t pytest` command beside the 3.14t one. Verify no sentence still describes a 3.14-only matrix.
- [x] 3.2 Verify no CHANGELOG entry is owed: nothing caller-visible changes and `requires-python` is untouched.

## 4. Validate as CI does

- [x] 4.1 Run `uv run --python 3.14t pytest`, then plain `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .` last, so the dev `.venv` ends up back on 3.14. Verify all pass.
- [x] 4.2 Run `openspec validate add-python-315-ci-legs --strict` and verify it reports valid.
- [x] 4.3 Run `git diff --stat` and verify it touches no file under `src/`.

## Recorded at implementation (2026-10-09)

- 1.3: the newest uv (0.12.24) resolved `3.15` to **3.15.0rc3** (`3.15t` to the
  rc3 free-threading build, `sys._is_gil_enabled()` False). 1154 passed on
  each, with no skips or xfails, the same count as 3.14 and 3.14t. Coverage on
  3.15 was **98.60%**, identical to 3.14, so 3.15's tracing doesn't shift
  branch counting.
- 1.4: ruff, ruff format, `ty` and pip-audit are clean on 3.15. Locally,
  pip-audit on 3.14 fails before auditing because the 3.14 interpreter the
  system uv provisions lacks `ssl`. That's a local-environment defect,
  identical on master, and doesn't apply to CI.
- 2.1: the wheel is `snakestream-…-py3-none-any.whl`, and
  `project.dependencies` is undeclared (empty). Both premises hold.
- Alongside 2.1: the `install_smoke_test` comment named
  `setuptools.build_meta` as the backend. It is `hatchling.build`
  (`pyproject.toml`), which the spec already said, so the comment was
  corrected.

## Workflow follow-up

- Archive the change (`/opsx:archive`). Then fix by hand the singular "its supported interpreter" in the Purpose line of `openspec/specs/free-threaded-support/spec.md`, which the delta can't reach.
- The roadmap item `support-python-315` stays **open** until a CI run's setup-uv log shows `3.15.0` final, not an rc, on both 3.15 legs. Then add the outcome to its prose, replacing the stale rc2 paragraph, and run `python tools/roadmap.py close support-python-315 --outcome shipped --as add-python-315-ci-legs`, `index` and `check`.
