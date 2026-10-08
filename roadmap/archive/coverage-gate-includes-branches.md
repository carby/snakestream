+++
id = "coverage-gate-includes-branches"
title = "Verified the coverage gate already counts branch coverage"
filed = 2026-08-10
closed = 2026-08-10
outcome = "shipped"
+++

Verified `--cov-fail-under=98` already enforces combined line+branch
coverage, not line coverage alone: `[tool.coverage.run] branch = true`
folds branch-arc misses into the same "percent covered" figure the gate
reads, confirmed by observing a deliberately partial branch drop the
reported percentage. No code change needed; added a comment in
`pyproject.toml` recording the finding so it doesn't need re-deriving.
