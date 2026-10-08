+++
id = "coverage-gate"
title = "Added a `--cov-fail-under=98` coverage gate"
filed = 2026-08-04
closed = 2026-08-04
outcome = "shipped"
+++

Added a `--cov-fail-under=98` gate so a coverage regression now fails CI
instead of silently passing. Enforced only on the newest Python version
in `check.yml`'s matrix (not via `setup.cfg`'s `addopts`), since
`coverage.py`'s branch-arc measurement for `async for` loops differs
across CPython versions and produced spurious failures on 3.8/3.9.
