## 1. Fix the message

- [x] 1.1 In `src/snakestream/stream.py`, `_check_not_consumed()`, change the `IllegalStateException` message from "this stream has already been extended into a new instance or terminally consumed" to "this stream has already been extended into a new instance", matching the `terminal-sinks` spec's wording.

## 2. Verify

- [x] 2.1 Run `uv run pytest` and confirm all tests pass with no test file edited (no test asserts the message text — verified 2026-08-24 against all eight `pytest.raises(IllegalStateException)` sites).
- [x] 2.2 Run `uv run ruff check .` and `uv run ruff format --check .`.
- [x] 2.3 Run `uv run ty check src`.
