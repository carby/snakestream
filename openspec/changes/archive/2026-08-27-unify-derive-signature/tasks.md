## 1. Widen `_derive()`

- [x] 1.1 Add the `executor: Executor | None = None` parameter to
      `Stream._derive()` in `src/snakestream/stream.py`, and set
      `new_stream._executor = executor or self._executor` in place of the
      current unconditional `new_stream._executor = self._executor`.
- [x] 1.2 Rewrite `_derive()`'s docstring to carry both derivation rules: that
      an omitted `op` yields a plain copy (what a mode switch derives from),
      that an omitted `executor` keeps the receiver's, and that on the no-op
      path the chain passes through by identity rather than being copied —
      safe only because the receiver is consumed on the way out and chains are
      only ever extended by copy.

## 2. Collapse the mode switches

- [x] 2.1 Reduce `sequential()` to `return self._derive(executor=SEQUENTIAL)`
      and `parallel()` to `return self._derive(executor=RACING)`.
- [x] 2.2 Trim `sequential()`'s docstring to the two rules only it records —
      that a mode switch must not compose (composing is what made
      `.parallel()` position-dependent), and must not flip in place and return
      `self` (pipeline-immutability requires the receiver be invalidated) —
      dropping the mechanics that moved to `_derive()`. Confirm `parallel()`
      still points at it.
- [x] 2.3 Grep `src/` and `tests/` for any remaining write to a `_executor` or
      `_chain` attribute outside `_derive()`; there should be none.

## 3. Verify

- [x] 3.1 `uv run pytest` — full suite green, with no test edits. If any test
      required a change, stop: this change is specified as behaviour-preserving
      and a required edit means it is not.
- [x] 3.2 `uv run ruff check .`, `uv run ruff format --check .`, and
      `uv run ty check src` all clean.
- [x] 3.3 `uv run pytest --cov-fail-under=98` passes, matching the CI gate.
- [x] 3.4 Retire the roadmap tripwire the 2026-08-26 `collapse-derive-wrappers`
      entry left behind — "`_executor` is no longer assigned exactly once per
      instance ... recorded so that adding an `await` to `_derive()` is
      recognised as breaking it" — since `executor or self._executor` restores
      the assign-once property that warning existed to guard.
- [x] 3.5 Confirm the CLAUDE.md paragraph describing `.parallel()` /
      `.sequential()` ("each derive with no op — `_derive()` with its `op`
      argument omitted — and assign `_executor` on the result") still reads
      true, and update the "assign `_executor` on the result" clause if not.
