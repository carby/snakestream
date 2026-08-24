## Why

`execution.py`, `sink.py` and `ops.py` are the three files a reader has to
hold in their head at once to understand how the chain-of-ops model executes,
but all three open straight into imports. The map that explains how they fit
together — the four execution primitives, the two executors, the op/sink
`begin`/`accept`/`end` protocol — lives only in `CLAUDE.md`, a file a reader
opening `execution.py` directly may never see. A short module docstring on
each file puts that orientation where a reader will actually hit it.

## What Changes

- Add a module docstring to `src/snakestream/execution.py`: names the four
  primitives (`stream_through`, `race_through`, `feed_through`, `drain`) and
  the two executors (`Sequential`, `Racing`), and notes that
  `Sequential.value()`'s override of the generic `drain(elements(...),
  terminal)` default is the one asymmetry in the protocol.
- Add a module docstring to `src/snakestream/sink.py`: names the op/sink pair
  and the `begin`/`accept`/`end` protocol a `Sink` implements.
- Add a module docstring to `src/snakestream/ops.py`: notes that the file
  holds one `Op` plus one `Sink` per intermediate operation, and that it
  contains no execution logic (that lives in `execution.py`).
- Each docstring is orientation (four or five lines), not a restatement of
  what the per-class docstrings in the same file already say.

## Capabilities

No spec-level behavior changes — this adds documentation only. No existing
requirement's observable behavior is affected.

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `src/snakestream/execution.py`, `src/snakestream/sink.py`,
  `src/snakestream/ops.py`: each gains a module-level docstring only; no
  runtime code changes.
- No public API surface change, no test behavior change expected.
- Corresponds to **Now** item 1 in `roadmap.md` (2026-08-24 legibility
  batch); see that entry's "Implementation notes for items 1-2" for the
  shared brief, tripwire (full suite green with no test file edited) and
  fences (do not let this drift into already-rejected dedup territory).
