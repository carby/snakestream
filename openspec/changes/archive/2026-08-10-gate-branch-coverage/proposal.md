## Why

CI enforces `--cov-fail-under=98` on the newest Python leg, and `[tool.coverage.run]` already sets `branch = true`, so the data exists — but nothing confirms the 98% gate is actually reading combined line+branch coverage rather than line coverage alone. An untested `if`/`else` side (a covered line, an uncovered branch) could currently slip through CI undetected.

## What Changes

- Verify (and document, via a code comment or the coverage config itself) that `--cov-fail-under=98` reflects combined line+branch coverage under `branch = true`, since `coverage.py` folds branch results into a single overall percentage rather than reporting them as a separate gate.
- If verification shows branches are *not* actually being enforced, add an explicit check (e.g. `coverage report --fail-under=98` reasoned about branch data, or a `fail_under` setting under `[tool.coverage.report]`) so a regression in branch coverage fails CI the same way a line-coverage regression does.
- Add a regression test that exercises both sides of a previously branch-uncovered conditional, if the verification step finds a real gap, so the fix is provable rather than just asserted.

## Capabilities

### New Capabilities
- `branch-coverage-gate`: CI enforcement that a pull request's combined line+branch test coverage does not regress below the configured threshold (currently 98%).

### Modified Capabilities
(none — no existing specs cover coverage enforcement)

## Impact

- `pyproject.toml` — `[tool.coverage.report]` / `[tool.pytest.ini_options]` `addopts`, if a config-only change is needed.
- `.github/workflows/check.yml` — the "Enforce coverage threshold" step, if the invocation needs to change.
- No production code or public API impact; test-and-CI-only change.
