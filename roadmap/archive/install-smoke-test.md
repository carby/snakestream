+++
id = "install-smoke-test"
title = "Added an `install_smoke_test` CI job"
filed = 2026-08-11
closed = 2026-08-11
outcome = "shipped"
+++

Added an `install_smoke_test` CI job (`.github/workflows/check.yml`) that,
for each of Python 3.10–3.14, creates a clean venv (`uv venv`, not
`uv sync`), runs `pip install .` against the built package, and imports
`snakestream` from outside the repo checkout — catching packaging
mistakes that the source-tree `pytest` job wouldn't.
