## Why

`stream.py:88` names the normalized `AsyncGenerator` source `self._stream`, while every function in `execution.py` that receives that same value (`stream_through`, `race_through`, `feed_through`, `_guarded`) names it `source`. Reading a call site like `self._executor.elements(self._chain, self._stream)`, a reader has to stop and work out whether `_stream` is the raw normalized source or something already composed — it isn't, but the name doesn't say so. Renaming the field to `self._source` makes every call site read as the `(chain, source)` pair the execution primitives already take, with the widest read-benefit per line changed of the five items in the 2026-08-24 legibility batch.

## What Changes

- Rename the private field `Stream._stream` to `Stream._source` throughout `stream.py` (declaration, `__init__`, `_derive`, `_compose`, `_evaluate`) — the only methods that reference it after the `_evaluate()`/`_derive()` consolidations already landed.
- No behavior change: this is a mechanical rename of a private attribute. No public API, no test, and no spec references `._stream` (verified 2026-08-24 — zero hits across `tests/`).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None — pure private rename, no spec-level behavior changes. `skip_specs: true` is set in this change's `.openspec.yaml`.

## Impact

- **Affected code**: `src/snakestream/stream.py` only (the field's declaration and its handful of internal reads/writes).
- **Affected tests**: none expected — no test file references `Stream._stream`, so the full suite must pass unedited.
- **Public API / README**: none — `_stream` is a private, unexported attribute.
