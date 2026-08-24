## 1. Document the deliberate self-mutation on `unordered()`/`on_close()`

- [x] 1.1 Add a one-line docstring note to `Stream.unordered()` (`stream.py:151`) stating it mutates and returns `self` by design, per the `stream-ordering` spec.
- [x] 1.2 Add a one-line docstring note to `Stream.on_close()` (`stream.py:158`) stating it mutates and returns `self` by design, per `pipeline-immutability` spec line 58.
- [x] 1.3 Confirm neither docstring restates logic already covered elsewhere; keep each to one line pointing at the spec.

## 2. Export `PROCESSES` from the top-level package

- [x] 2.1 Add `from snakestream.execution import PROCESSES as PROCESSES` to `src/snakestream/__init__.py`.
- [x] 2.2 Add a test asserting `from snakestream import PROCESSES` succeeds and equals `snakestream.execution.PROCESSES`.
- [x] 2.3 Update README's parity/export table if it lists top-level exports elsewhere, so the entry matches the new import path (no wording change expected to the `.parallel()`/`PROCESSES` prose itself). No such table exists; only prose mentions, which already read correctly — no edit needed.

## 3. Drop the dead `pylint` pragmas in `collector.py`

- [x] 3.1 Re-confirm no `pylint` config or invocation exists anywhere in the repo (`pyproject.toml`, CI workflows, `.pylintrc`). Confirmed: only comment pragmas remain in `collector.py` and two test files (out of scope), no config or tool invocation anywhere.
- [x] 3.2 Delete the four `# pylint: disable=...` lines at the top of `collector.py` (lines 1-4).

## 4. Verify

- [x] 4.1 `uv run ruff check .` and `uv run ruff format --check .` pass.
- [x] 4.2 `uv run ty check src` passes.
- [x] 4.3 `uv run pytest` passes with only the one new test file/assertion from 2.2 added — no existing test file edited. 536 tests pass, 98% coverage.
- [x] 4.4 `openspec validate --strict` passes for this change.
