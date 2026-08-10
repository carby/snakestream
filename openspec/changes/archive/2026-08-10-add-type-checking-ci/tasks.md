## 1. Evaluate `ty`

- [x] 1.1 Run `uv run --with ty ty check src` locally against the current codebase and review the output.
- [x] 1.2 Assess whether `ty` handles the `Awaitable`-union type aliases in `type.py` and the `TYPE_CHECKING`-guarded import in `stream.py` without excessive false positives or crashes.
- [x] 1.3 Decide: proceed with `ty`, or fall back to `mypy`/`pyright` if `ty` proves unworkable. Record the decision.

## 2. Fix or triage findings

- [x] 2.1 Fix genuine type errors surfaced by the checker in `src/snakestream`.
- [x] 2.2 For any finding that's a checker limitation rather than a real bug, add a scoped inline ignore with a comment explaining why.
- [x] 2.3 Confirm the checker runs clean (zero errors) against `src/snakestream` after fixes.

## 3. Wire into the project

- [x] 3.1 Add the chosen checker to `[dependency-groups] dev` in `pyproject.toml`.
- [x] 3.2 Add any needed config section (e.g. `[tool.ty]`, `[tool.mypy]`, or `[tool.pyright]`) to `pyproject.toml` — not needed, `ty` runs clean with defaults.
- [x] 3.3 Add a "Type check" step to the `code_check` job in `.github/workflows/check.yml`, gated to a single Python version (matching the `if matrix.python-version == '3.14'` pattern used for `pip-audit` and the coverage gate).

## 4. Document and validate

- [x] 4.1 Update `CLAUDE.md`'s command reference to include the new local type-check command.
- [x] 4.2 Update `roadmap.md`: move this item from **Now** to **Done**, noting which checker was chosen and why.
- [x] 4.3 Run the new type-check command locally and confirm it passes.
- [x] 4.4 Run `uv run pytest`, `uv run ruff check .`, and `uv run ruff format --check .` to confirm no regressions from any code changes made while fixing type errors.
