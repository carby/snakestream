## 1. Add the install smoke test job to CI

- [x] 1.1 Add a new `install_smoke_test` job to `.github/workflows/check.yml`, matrixed on Python 3.10–3.14, using `astral-sh/setup-uv` (same pinned action as `code_check`) purely to provision the interpreter.
- [x] 1.2 In the job, create a fresh virtual environment (`uv venv --python <version>`, since plain `setup-uv` doesn't put a matching `python` on PATH) and activate it.
- [x] 1.3 Run `pip install .` against the checked-out repo inside that fresh venv.
- [x] 1.4 Add a step that `cd`s to a directory outside the repo checkout (e.g. `$RUNNER_TEMP`) and runs `python -c "import snakestream"` to verify the installed package imports without relying on the repo's `src/` layout.
- [x] 1.5 Add `permissions: contents: read` / confirm the job inherits the workflow-level concurrency group already set in `check.yml`.

## 2. Validate

- [ ] 2.1 Push the branch and confirm the new job runs and passes on all 5 matrix legs.
- [x] 2.2 Verified locally: a fresh venv + `pip install .` + `import snakestream` succeeds and resolves from the installed distribution (not `src/`); a failing import (`ModuleNotFoundError`) exits non-zero, which fails a GH Actions `run` step by default — no extra error handling needed in the workflow.
- [x] 2.3 Update `roadmap.md` — move the "Add an install/import smoke test" item from **Now** to **Done** with a short summary of what was added.
