+++
id = "support-python-315"
title = "Test on Python 3.15 in CI"
bucket = "now"
rank = 1
filed = 2026-10-09
gate = "CPython 3.15.0 final is released and installable through uv"

[refs]
files = [".github/workflows/check.yml", ".github/workflows/deliver.yml"]
+++

CI tests only Python 3.14: `code_check` runs a GIL-enabled `3.14` leg and a
free-threaded `3.14t` leg, and `install_smoke_test` and `deliver.yml` run on
`3.14` alone. `requires-python = ">=3.14"` already admits 3.15, so once 3.15 is
released, snakestream claims to support an interpreter it has never been tested
on. Most at risk is the free-threaded build. Real CPU parallelism under
`.parallel()` depends on it (PEP 779), and the fork/join executor's thread
dispatch is exactly the code a change to the free-threaded runtime could break.

Done looks like:

- `code_check` gains `3.15` and `3.15t` legs next to the 3.14 pair, and both
  pass `uv run pytest` and the ruff checks.
- The single-leg steps are placed deliberately. `ty`, `pip-audit` and the
  coverage gate run on one GIL-enabled leg, and `CLAUDE.md` says the coverage
  gate runs on the newest interpreter, which suggests moving them to `3.15`.
  `CLAUDE.md`'s description of the CI legs is updated to match.
- `install_smoke_test` and `deliver.yml` either move to `3.15` or test both
  versions, with the choice recorded here when the item closes.

Out of scope: raising `requires-python` or ruff's `target-version`. Either one
drops 3.14, which is a separate decision, like the earlier floor sequence
(`python-floor-sequence` in `done.md`).

The gate is the 3.15.0 final release. On 2026-10-09 uv offered only
`3.15.0rc2`, which is enough to trial the legs before then but not to ship them.
