## 1. Consolidate close_handlers initialization

- [x] 1.1 Add a `close_handlers: list[CloseHandler] | None = None` parameter to `BaseStream.__init__` (`base_stream.py:30`), setting `self._close_handlers = close_handlers or []` there instead of the current unconditional `self._close_handlers = []`.
- [x] 1.2 Update `Stream.__init__` (`stream.py:103-105`) to pass `close_handlers` through to `super().__init__(source, close_handlers)` and drop its own `self._close_handlers = close_handlers or []` reassignment.
- [x] 1.3 Update `ParallelStream.__init__` (`parallel_stream.py:25-27`) the same way.

## 2. Verify no behavior change

- [x] 2.1 Run the full test suite (`uv run pytest`) and confirm existing tests covering `on_close()`/`close()` and stream construction with/without `close_handlers` pass unmodified.
- [x] 2.2 Add tests covering the `stream-close-handling` spec's scenarios not already exercised: registration order preserved across multiple `on_close()` calls, `close()` with zero handlers is a no-op, `Stream(source, [handler])` construction invokes the handler, and close handlers survive both `sequential()` and `parallel()` mode switches.
- [x] 2.3 Run `uv run ruff check .`, `uv run ruff format --check .`, and `uv run ty check src` to confirm lint/format/type gates pass.
- [x] 2.4 Run `uv run pytest --cov-fail-under=98` to confirm the coverage gate still passes.

## 3. Documentation

- [x] 3.1 Move this roadmap item from `roadmap.md`'s **Now** table to **Done**, following the existing Done-entry format, and link to this change's archive location per `CLAUDE.md`'s feature-parity tracking convention.
