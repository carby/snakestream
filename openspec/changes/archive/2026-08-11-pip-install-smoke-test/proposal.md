## Why

CI only runs `uv sync` + `pytest` against checked-out source with dev dependencies present. It never builds the sdist/wheel and installs it the way a real consumer would (`pip install .` then `import snakestream`), so a packaging mistake — a missing package in `packages`/`include`, a broken `dynamic` version resolution, a stray dependency only present in the dev group — could pass CI today while breaking on every real install. This is called out as the top item in `roadmap.md`'s Now list: low effort, closes a real gap.

## What Changes

- Add a new CI job (or step) that builds the package and installs it into a clean virtual environment via `pip install .` — not `uv sync` against the checked-out source tree — then runs `python -c "import snakestream"` to catch import-time failures.
- Run this smoke test across the same Python matrix already used for the main `code_check` job (3.10–3.14), since packaging/import issues can be interpreter-specific (e.g. `dynamic` version resolution, C-extension-free but still worth covering per-version).
- Wire the new job/step into `.github/workflows/check.yml` so it's a required part of the existing `Check` workflow, not a separate opt-in workflow.

## Capabilities

### New Capabilities
- `install-smoke-test`: CI verification that the packaged distribution installs cleanly via `pip install .` and that `import snakestream` succeeds, run across the full supported Python matrix.

### Modified Capabilities
(none — no existing spec's requirements change)

## Impact

- Affected files: `.github/workflows/check.yml` (new job or steps).
- No source code changes required unless the smoke test surfaces a real packaging bug.
- Slightly increases CI wall-clock time (one extra build+install per matrix leg); no new runtime dependencies for the package itself, only a CI-time build step (`build` or equivalent, or plain `pip install .` which invokes the existing `setuptools.build_meta` backend directly).
