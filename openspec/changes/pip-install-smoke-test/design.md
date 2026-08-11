## Context

`check.yml`'s `code_check` job runs `uv sync` (which installs the project in editable mode alongside dev dependencies from the lockfile) and then `uv run pytest`. That path never exercises `setuptools.build_meta`'s actual build (`pyproject.toml` `dynamic = ["version"]`, package discovery) or a plain `pip install .` into an environment with no dev extras. A regression there (e.g. a module missing from the built wheel, a version-resolution failure since versioning is `dynamic`) would only surface after a real `pip install snakestream` by an end user, not in CI.

## Goals / Non-Goals

**Goals:**
- Catch install/import-time packaging breakage in CI before it reaches an end user.
- Cover the same Python matrix (3.10–3.14) already gated on, since packaging/import behavior can vary per-interpreter.
- Keep the check cheap and isolated — it should not replace or slow down the existing `uv sync` + `pytest` path.

**Non-Goals:**
- Not testing runtime behavior of the library post-install — the existing pytest suite (run against source) already does that.
- Not testing installation from PyPI/TestPyPI (that's `deliver.yml`'s concern) — this is a local `pip install .` from the checked-out source, run in CI on every push.
- Not adding a new standalone workflow file; this extends `check.yml`.

## Decisions

- **Add a new job `install_smoke_test` in `check.yml`, matrixed on the same Python versions, rather than a step inside `code_check`.** `code_check` uses `uv sync` which installs the project editable alongside the full dev dependency group in the same venv `uv` manages; interleaving a separate `pip install .` into that same environment risks polluting or conflicting with it. A separate job gets a clean venv per matrix leg for free and runs in parallel, adding no net wall-clock time to the workflow (only extra runner-minutes, which is acceptable per `roadmap.md`'s "low effort" framing).
- **Use `uv venv --python <version>` to create the venv, then plain `pip install .` inside it, not `uv sync`, for the install step.** The whole point is to exercise the code path a real end user hits (`pip install snakestream`), which `uv sync`'s editable/dev-group install does not represent. `astral-sh/setup-uv`'s `python-version` input only sets `UV_PYTHON` for `uv` commands — it does not put a matching `python` on `PATH`, so a bare `python -m venv` isn't guaranteed to pick the matrix version. `uv venv --python <version>` is used instead to provision a correctly-versioned interpreter into the venv; the install itself (`pip install .`, run after `source .venv/bin/activate`) is plain `pip`, not `uv pip`.
- **Smoke-test command is `python -c "import snakestream"` after install, run from a directory other than the repo root.** Running from repo root risks accidentally importing the local `src/` layout via `sys.path[0]` rather than the installed package, which would defeat the purpose of the test. `cd` to a scratch/tmp directory (or `$RUNNER_TEMP`) before the import check.
- **No new production dependency.** `pip install .` invokes the `setuptools.build_meta` backend already declared in `pyproject.toml`; no `build` package or wheel-building tool needs to be added.

## Risks / Trade-offs

- [Extra CI runner-minutes from a second matrix'd job] → Acceptable per roadmap's own "low effort" characterization; each leg only does a venv create + pip install + one-line import, no test suite run.
- [Job could pass by accidentally still resolving to the repo's `src/` via a stray `PYTHONPATH` or leftover `uv`-managed venv] → Mitigated by using a fresh `python -m venv` and running the import check from outside the repo working directory.
- [Divergence between `check.yml` (per-push smoke test) and `deliver.yml` (actual PyPI publish)] → Out of scope here; this only closes the CI gap, not the release-verification gap, which is a separate concern if desired later.

## Migration Plan

No user-facing migration. Additive CI-only change:
1. Add the new job to `check.yml`.
2. Confirm it passes on all 5 matrix legs.
3. Merge — no rollback complexity beyond reverting the workflow diff if it proves flaky.

## Open Questions

None outstanding — scope is intentionally narrow (CI-only, no code changes expected).
