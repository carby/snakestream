## 1. `_Window` holds slots

- [x] 1.1 Add `outstanding` to `_Window.__slots__` and `__init__`, initialised
  to 0; keep `assigned`, `released`, `size` and `event`. Verify
  `uv run pytest tests/test_racing_encounter_order.py` still passes with the
  field unread.
- [x] 1.2 Add `take() -> bool`: return False when `outstanding >= size`,
  otherwise increment and return True. Its docstring states the atomicity and
  its cause — no `await` in the body, so nothing can run between the check and
  the increment — in the same terms `_LimitSink.accept()` states its own
  reserve-before-push. Verify by inspection that the body contains no `await`.
- [x] 1.3 Add `give_back()`: decrement `outstanding` and set `event`. Verify it
  is the mirror of the claim, not of `release_one()` — it advances no cursor.
- [x] 1.4 Extend `release_one()` to decrement `outstanding` alongside its
  existing `released += 1` and `event.set()`. Verify
  `tests/test_racing_encounter_order.py::test_a_head_op_that_emits_at_end_is_
  ordered_after_every_real_group`, which drives `_Window` and
  `_release_in_order()` directly, still passes.
- [x] 1.5 Delete `full()` and update `_Window`'s class docstring: it now
  documents three counters with one job each (index, cursor, occupancy) and
  why occupancy can no longer be derived from the other two (design.md
  Decision 2). Verify `uv run ruff check .` reports no unused member.

## 2. `_guarded()` claims before the lock

- [x] 2.1 Replace the windowed arm's doubly-nested loop with: wait outside the
  lock until `take()` succeeds, then pull and assign the index under the lock.
  The wait-outside-the-lock comment stays and keeps its reason; the post-lock
  re-check, its `continue` arm and the outer `while True` all go. Verify
  `uv run pytest tests/test_racing_encounter_order.py
  tests/test_racing_delivery_order.py tests/test_find_first.py` passes.
- [x] 2.2 Call `window.give_back()` before returning on the windowed
  `StopAsyncIteration` path, with a comment naming what it prevents (a claimed
  slot that no group will ever release — design.md Decision 4). Verify
  `test_branches_contending_for_the_last_window_slot_still_pull_in_order`
  passes, which runs a window of one to exhaustion and would stall on a leak.
- [x] 2.3 Verify the unwindowed arm is byte-identical to before
  (`git diff` shows no hunk touching it).
- [x] 2.4 Update `_guarded()`'s docstring where it describes the bound being
  enforced at index assignment: the claim now happens before the pull, which
  is what makes the bound conservative rather than exact (design.md
  Decision 3). Verify the docstring no longer describes a re-check.

## 3. Gate and verification

- [x] 3.1 Re-run the design.md Decision 1 harness against the shipped code —
  live-module patching, 20,000 elements, `map(x + 1)`, 4 workers,
  `_CountSink`, 10 interleaved rounds, three runs — and confirm the
  ordered-delivery delta still straddles zero and is inside the `+10%`
  ns/element gate. Record any drift from the table in design.md.
- [x] 3.2 Run `uv run pytest` and verify 988 tests pass with
  `git diff --stat tests/` empty — no test file, name or import touched.
- [x] 3.3 Run `uv run ruff check .`, `uv run ruff format --check .` and
  `uv run ty check src`; all clean.
- [x] 3.4 Verify coverage against `uv run pytest --cov-fail-under=98`, and
  confirm `execution.py`'s missed statements and partial branches are no worse
  than before — the removed re-check arm was covered, so its branches must
  disappear rather than go unreached.
