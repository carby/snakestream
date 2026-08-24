## 1. Rename

- [x] 1.1 Rename `Stream._stream` to `Stream._source` in `src/snakestream/stream.py`: the field declaration/annotation, `__init__`, `_derive`, `_compose`, and `_evaluate` (and any other reference the checker finds).
- [x] 1.2 Grep `src/` and `tests/` for `._stream` and `_stream` (excluding unrelated hits like `stream_through`, `race_through`, module name `stream.py`) to confirm no stray reference remains and no test touches the field.

## 2. Verify

- [x] 2.1 Run `uv run pytest` — full suite must pass with **no test file edited**.
- [x] 2.2 Run `uv run ruff check .` and `uv run ruff format --check .`.
- [x] 2.3 Run `uv run ty check src`.
- [x] 2.4 Run `openspec validate --strict` for this change.
