## Why

`_Window` and `_guarded()` (`src/snakestream/execution.py`) hand-roll a
counting semaphore out of a counter and an `asyncio.Event`, and get the
primitive wrong: an `Event` broadcasts "something changed" but cannot *hold* a
slot. So a branch that waits for room must ask again after taking the lock,
because another branch may have taken the last slot in between — and that
re-check forces a doubly-nested `while True`, a `clear()`/`wait()` protocol,
and a correctness subtlety with a regression test of its own
(`test_branches_contending_for_the_last_window_slot_still_pull_in_order`).

The slot is what the code actually wants to acquire. Making the take atomic
removes the barging window rather than compensating for it.

## What Changes

- `_Window` gains an `outstanding` count and a synchronous `take()` that
  atomically claims a slot when one is free — atomic because it contains no
  `await`, so no other task can run between its check and its increment —
  plus `give_back()` for the one path that claims a slot and produces no
  group. `size` and `event` stay; `full()` goes.
- `_guarded()`'s windowed arm loses one loop level, the post-lock re-check and
  the `continue` arm that fed it. It becomes: wait outside the lock until
  `take()` succeeds, then pull and assign under the lock.
- A branch whose pull raises `StopAsyncIteration` returns its claimed slot.
  Today no slot is claimed on that path, because a slot is only taken at index
  assignment; under an up-front take one is, and it must not leak.
- No change to the unwindowed arm, to the bound's value or scaling, to which
  elements are pulled, or to anything a caller can observe.

**Not taken: `asyncio.Semaphore` itself**, which is the same semantics from the
standard library and was this change's first candidate. It measured a
consistent +4…+7% per element on the ordered-delivery path across three runs,
because `acquire()` is an `async def` and costs a coroutine frame per pull even
on its synchronous fast path. `take()` is the semaphore's contract without the
frame, and measured free. See design.md for the figures.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. `racing-encounter-order`'s read-ahead requirements describe the bound's
existence, its scaling with the branch count and its fixedness for a run; all
three hold unchanged, and the change is invisible above `_guarded()`.
`skip_specs: true`.

## Impact

- `src/snakestream/execution.py` only: `_Window` and `_guarded()`.
- No public surface, no import, no name a test reads.
  `_Window(size)`'s constructor signature is unchanged, so
  `tests/test_racing_encounter_order.py`'s direct construction and its
  `monkeypatch` of `_in_flight` are untouched.
- Per-element path of the windowed (barrier) arm, so the
  `collapse-terminal-collector-duplication` gate of +10% ns/element applies and
  is measured in design.md.
