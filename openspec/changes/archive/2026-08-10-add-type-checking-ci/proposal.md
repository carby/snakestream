## Why

The codebase is fully type-hinted, but nothing in CI actually checks that the hints stay accurate — type errors can drift in silently. `ty`, Astral's newer Rust-based type checker, is worth trying alongside the more established `mypy`/`pyright` options given the project already uses Astral's `ruff` and `uv` toolchain.

## What Changes

- Evaluate `ty` against the codebase locally: run it, review the findings, and judge signal quality (false positives, coverage of the `async`/`await`-heavy, `Awaitable`-typed code in `type.py`).
- If `ty` proves workable, add it as a dev dependency and wire it into CI (`.github/workflows/check.yml`) as a new step, matching the existing pattern of dependency groups in `pyproject.toml`.
- If `ty` finds real type errors in the current codebase, fix them as part of adding the gate (small, type-only fixes) or, if fixes are non-trivial, suppress with justified inline ignores and note them for follow-up — do not merge a gate that starts red.
- If `ty` proves immature or unworkable for this codebase (e.g. can't handle the `Awaitable`-union aliases in `type.py`, or the `TYPE_CHECKING`-guarded import in `stream.py`), fall back to `mypy` or `pyright` instead — the roadmap item is "add a type checker," not "add `ty` specifically."

## Capabilities

### New Capabilities
- `static-type-checking`: CI enforcement that type hints across `src/snakestream` remain internally consistent, checked by a static type checker on every push.

### Modified Capabilities
(none — no existing specs cover type checking)

## Impact

- `pyproject.toml` — new `[dependency-groups] dev` entry for the chosen type checker; possibly new `[tool.ty]` (or `[tool.mypy]`/`[tool.pyright]`) config section.
- `.github/workflows/check.yml` — new "Type check" step in the `code_check` job.
- Possibly `src/snakestream/*.py` — small type-hint fixes if the checker surfaces real drift.
- No runtime/public API impact; dev-tooling and CI-only change.
