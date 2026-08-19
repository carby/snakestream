## Why

`src/snakestream/stream.py` is 485 lines of two unrelated concerns: lines 44–223
are the eight op/sink pairs that make up the execution layer, and lines 226–485
are the public `Stream` API. Someone opening the file to find the public surface
scrolls past the whole execution layer first. The op-collapse change that just
landed reduced the op half to eight two-to-four-line declarations, so this is now
a pure move — cut the two blocks, add the imports, change nothing else.

## What Changes

- Add `src/snakestream/ops.py` holding the eight op/sink pairs moved verbatim out
  of `stream.py`: `_FilterSink`/`_FilterOp`, `_MapSink`/`_MapOp`,
  `_PeekSink`/`_PeekOp`, `_SortedSink`/`_SortedOp`, `_FlatMapSink`/`_FlatMapOp`,
  `_DistinctSink`/`_DistinctOp`, `_LimitSink`/`_LimitOp`, `_SkipSink`/`_SkipOp`.
- `stream.py` imports the eight op classes from `snakestream.ops`; its own
  imports shrink to what the public `Stream` API still uses.
- `tests/test_op_protocol.py` imports the eight op classes from `snakestream.ops`
  instead of `snakestream.stream`.
- No behavior change, no public API change. Every name moved is private and
  unexported, so README's parity tables need no edit.

## Capabilities

### New Capabilities

None. This is a pure file-organization refactor with no spec-level behavior
change, so the change sets `skip_specs: true` in its `.openspec.yaml`.

### Modified Capabilities

None. `sink-protocol` and `pipeline-composition` describe the op/sink protocol in
terms of the protocol classes in `sink.py`, not the module the eight concrete ops
live in, so neither spec's requirements change.

## Impact

- `src/snakestream/stream.py` — loses ~180 lines and several now-unused imports.
- `src/snakestream/ops.py` — new file.
- `tests/test_op_protocol.py` — import path update.
- No change to `base_stream.py`, `parallel_stream.py`, `sink.py`, `collector.py`,
  `README.md`, or any packaging metadata (the package is imported as a whole; no
  per-module entry points exist).
