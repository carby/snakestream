## Why

Story 3 of the 2026-08-25 batch: four small legibility and stdlib-usage
findings that all live behind the public surface and none of which change
observable behaviour.

The largest is repetition with no home. All eight intermediate operations in
`stream.py` (`filter`, `map`, `flat_map`, `sorted`, `distinct`, `peek`,
`limit`, `skip`) are the same 90-column line —
`cast("Stream[X]", self._derive(self._chain + [_SomeOp(...)], self._executor))`
— differing only in the `Op` constructed. The chain-extension rule
("a new op is appended to a copy of the chain, under the same executor") is
therefore written eight times, and the one thing each method is actually
*about* (which `Op` it queues) is the least visible part of the line. The other
three findings are a dead override, an unannotated parameter, and a
non-preferred `asyncio` spelling.

## What Changes

- **(a)** Add a private `Stream._extend(op)` holding `self._derive(self._chain
  + [op], self._executor)`. Each of the eight intermediate ops becomes a
  one-line `return self._extend(_SomeOp(...))`, so `self._chain + [op]` and
  the executor-carry-forward are written once. The eight `cast(...)` wrappers
  go with them: `_extend` returns `Stream[Any]`, which is assignable to each
  method's declared return type without a cast (verified with `ty`).
  `flat_map`'s pre-call `iscoroutinefunction` rejection stays exactly where it
  is; `_extend` replaces only its return expression.
- **(b)** Delete `_ForEachSink._finish` (`terminals.py:52`). It returns `None`
  for a container that `_create_container` already always makes `None`, so it
  restates `TerminalSink._finish`'s inherited `return container` with a value
  that is identical in this sink.
- **(c)** Annotate `sorted(..., reverse: bool = False)` (`stream.py:255`) — the
  only unannotated parameter left in `stream.py`, on a file `ty` checks in CI.
- **(d)** `asyncio.ensure_future` -> `asyncio.create_task` at
  `execution.py:159` and `execution.py:172`. Both arguments are
  `branch.__anext__()`, always a coroutine, so `create_task` is the
  documented-preferred spelling and skips `ensure_future`'s type dispatch.
- No behaviour change, no public API change, no new or changed requirement.

## Capabilities

### New Capabilities

None. Every edit is behaviour-preserving and behind the public surface, so the
change sets `skip_specs: true` in its `.openspec.yaml` — the same treatment as
`split-ops-into-ops-module`, `collapse-terminal-drive-loop` and
`collapse-collector-sink-duplication`.

### Modified Capabilities

None. `pipeline-composition` and `pipeline-immutability` state what an
intermediate operation must do (queue an op, return a new stream, consume the
receiver); `_extend` changes where that is written, not what it does.
`terminal-sinks` and `sink-protocol` state the begin/accept/end/result
contract that (b)'s deletion leaves numerically identical. `stream-ordering`
and `stream-execution-model` are untouched by (d), which changes neither the
tasks created nor the order they complete in. Every existing requirement holds
unchanged, which is the acceptance criterion for the refactor.

## Impact

- `src/snakestream/stream.py` — new private `_extend()`; the eight
  intermediate ops shrink to one call each; `sorted`'s `reverse` gains `: bool`.
  This is the widest diff in the change, and the reason story 3 was sequenced
  after stories 1 and 2, which also edited this file.
- `src/snakestream/terminals.py` — `_ForEachSink._finish` removed.
- `src/snakestream/execution.py` — two `ensure_future` -> `create_task`
  substitutions inside `race_through()`. **(d) is the only per-element site in
  this change** (once per element per racing branch). It is a one-word
  substitution on the same object graph with no allocation difference, so it
  does not pull the change into the benchmark gate — but a diff there that
  grows past the substitution is a signal the change went wrong.
- `tests/` — **no test file may be edited.** The full suite passing untouched
  is this change's entire verification story; a needed test edit means the
  change altered behaviour and is the tripwire to stop on.
- `README.md` — no edit. Every name involved is private and unexported, and no
  parity table entry changes.
- `roadmap.md` — story 3 moves from **Now** to **Done**.
