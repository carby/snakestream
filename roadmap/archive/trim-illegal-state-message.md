+++
id = "trim-illegal-state-message"
title = "Trimmed the `IllegalStateException` message to drop \"or terminally consumed\""
filed = 2026-08-24
closed = 2026-08-24
outcome = "shipped"
+++

**Trimmed the `IllegalStateException` message to drop "or terminally
consumed"** (2026-08-24). `stream.py:97` read "this stream has already been
extended into a new instance **or terminally consumed**", but `_consumed =
True` is only ever set by `_derive()`, the shared copier behind the eight
intermediate ops and `.parallel()`/`.sequential()` — never by a terminal.
`pipeline-immutability` spec explicitly requires a merely-terminally-consumed
stream to stay usable, and `terminal-sinks` spec already worded the scenario
without the "or terminally consumed" clause; only the exception string
disagreed with both.

One-line change to `_check_not_consumed()`, scoped to the message string.
`skip_specs: true`: the specs already described the correct behavior, so
nothing in `openspec/specs/` changed. No test asserts the message text
(verified 2026-08-24 against all eight `pytest.raises(IllegalStateException)`
sites across `test_pipeline_immutability.py` and `test_execution_model.py`),
so 535 tests passed with **no test file edited**; `ruff`, `ruff format
--check` and `ty check src` all pass. Off the per-element path (raised only
on reuse of a consumed stream reference), so no benchmark gate applied. See
`openspec/changes/archive/2026-08-24-fix-illegal-state-exception-message`.
