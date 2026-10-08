+++
id = "rename-stream-to-source"
title = "Renamed `Stream._stream` to `Stream._source`"
filed = 2026-08-24
closed = 2026-08-24
outcome = "shipped"
+++

**Renamed `Stream._stream` to `Stream._source`** (2026-08-24). `stream.py`
named the normalized `AsyncGenerator` source `self._stream`, while every
function in `execution.py` that receives the same value (`stream_through`,
`race_through`, `feed_through`, `_guarded`) names it `source` — reading
`self._executor.elements(self._chain, self._stream)` required stopping to
work out whether `_stream` was the raw source or something already
composed. Now every call site reads as the `(chain, source)` pair the three
execution primitives already take.

Pure private rename, scoped to `stream.py`'s field declaration, `_derive`,
`_compose` and `_evaluate` — the only methods referencing it after the
`_evaluate()`/`_derive()` consolidations. `skip_specs: true`: no
spec-level behavior changed, only an internal attribute's name. 535 tests
green with **no test file edited** (a grep for `_stream` across `src/` and
`tests/` confirmed zero references before archiving, matching the item's
own prediction); `ruff`, `ruff format --check` and `ty check src` all pass.
Off the per-element path (read once per composition or drive-entry), so no
benchmark gate applied. See
`openspec/changes/rename-stream-source-field`.
