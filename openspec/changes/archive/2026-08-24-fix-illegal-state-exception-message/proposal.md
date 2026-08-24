## Why

`stream.py:97`'s `IllegalStateException` message reads "this stream has already been extended into a new instance **or terminally consumed**", but `_consumed = True` is only ever set by the two derive paths (`_derive()`, used by every intermediate op and by `.parallel()`/`.sequential()`) — never by a terminal operation. The `pipeline-immutability` spec explicitly requires that a merely-terminally-consumed stream stay reusable, and `terminal-sinks` spec already words the scenario without the "or terminally consumed" clause. Anyone who hits this exception and reads "terminally consumed" will go looking for the terminal call that set the flag and find none — a real, avoidable debugging cost for a one-line fix.

## What Changes

- Trim the `IllegalStateException` message in `stream.py:97` to drop "or terminally consumed", matching the wording `terminal-sinks` spec already uses ("has already been extended into a new instance").

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None — no spec-level behavior changes. The specs already describe the correct behavior (a terminally-consumed stream stays usable); only the exception string in the implementation is being brought into line with them. `skip_specs: true` is set in this change's `.openspec.yaml`.

## Impact

- `src/snakestream/stream.py`: one string literal changes, inside `_check_not_consumed()`.
- No test asserts the message text (verified 2026-08-24: all eight `pytest.raises(IllegalStateException)` sites across `test_pipeline_immutability.py` and `test_execution_model.py` match on exception type only), so no test file needs editing.
- No public API change, no migration-log entry.
