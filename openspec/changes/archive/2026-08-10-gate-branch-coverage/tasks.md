## 1. Verify current enforcement behavior

- [x] 1.1 Locally introduce a scratch conditional (e.g. temporarily edit a function to add an `if`/`else` where only one branch is exercised by existing tests) and run `uv run coverage report` / `uv run pytest --cov-fail-under=98` to observe whether the missing branch drops the reported percentage and fails the gate.
- [x] 1.2 Revert the scratch conditional; record the finding (gate already combined vs. gate is line-only).

## 2. Close the gap (only if verification finds line-only enforcement)

Not applicable — verification (1.1) confirmed the gate is already combined; no code changes made.

- [x] 2.1 ~~Replace or supplement the `--cov-fail-under=98` CLI flag with `[tool.coverage.report] fail_under = 98`~~ — skipped, not needed.
- [x] 2.2 ~~Update `.github/workflows/check.yml`'s "Enforce coverage threshold" step~~ — skipped, not needed.
- [x] 2.3 ~~Add a regression test exercising the previously-uncovered branch~~ — skipped, not needed.

## 3. Document the outcome

- [x] 3.1 Add a short comment next to `[tool.coverage.run] branch = true` in `pyproject.toml` stating that the enforced `fail_under`/`--cov-fail-under` threshold reflects combined line+branch coverage.
- [x] 3.2 Update `roadmap.md`: move this item from **Now** to **Done** with a one-line summary of the finding and any change made.

## 4. Validate

- [x] 4.1 Run `uv run pytest --cov-fail-under=98` locally and confirm it passes on the current (non-scratch) codebase.
- [x] 4.2 Run `uv run ruff check .` and `uv run ruff format --check .` if `pyproject.toml` was edited.
