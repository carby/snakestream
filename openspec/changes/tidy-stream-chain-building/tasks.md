## 1. `_extend()` and the eight intermediate operations

- [x] 1.1 Add a private `_extend(self, op: Op) -> Stream[Any]` to `Stream`,
      returning `self._derive(self._chain + [op], self._executor)`. Place it
      next to `_derive()` (`stream.py:114`). No `_check_not_consumed()` call —
      `_derive()` already runs it (design Decision 1).
- [x] 1.2 Rewrite the seven single-expression intermediates — `filter`, `map`,
      `sorted`, `distinct`, `peek`, `limit`, `skip` (`stream.py:240-268`) — as
      `return self._extend(_SomeOp(...))`, dropping the `cast()` wrapper and
      keeping each declared return type verbatim (`Stream[T]` vs. `Stream[R]`).
- [x] 1.3 Rewrite `flat_map`'s return expression only (`stream.py:253`). Its
      `iscoroutinefunction` guard, the `StreamBuildException` it raises and the
      comment above it stay exactly as they are (design Risk 1).
- [x] 1.4 Confirm the `cast` import in `stream.py` is still used
      (`sequential()`, `parallel()`, `iterate()`) and left in place.
- [x] 1.5 Run `uv run ty check src` — no new diagnostic. This, not the suite,
      is what proves the cast removal safe (design Decision 2).
- [x] 1.6 Run `uv run pytest` — green with **no test file edited**. Then
      `git status` on `tests/` to confirm it is clean.
- [x] 1.7 Commit 1 of 4, message carrying Decision 1 and 2's rationale (why a
      built `Op` rather than the pieces; why the casts were never needed).

## 2. `_ForEachSink._finish`

- [x] 2.1 Delete `_ForEachSink._finish` (`terminals.py:52-53`). Leave
      `_create_container` — it is `@abstractmethod` on `TerminalSink`.
- [x] 2.2 Grep `terminals.py` for any other `_finish` override that returns
      `None` for a `None` container; if one exists, note it for a later story
      rather than widening this task.
- [x] 2.3 Run `uv run pytest tests/test_for_each.py` and then the full suite —
      green, no test edited.
- [x] 2.4 Commit 2 of 4, message carrying design Decision 3 (the container is
      provably `None`, so the override is an identity) so `git log -S_finish`
      answers it later.

## 3. `sorted`'s `reverse` annotation

- [x] 3.1 Change `reverse=False` to `reverse: bool = False` in `Stream.sorted`
      (`stream.py:255`).
- [x] 3.2 Confirm `stream.py` now has no unannotated parameter left (scan the
      signatures; `self` excepted).
- [x] 3.3 Run `uv run ty check src` and `uv run ruff format --check .`.
- [x] 3.4 Commit 3 of 4.

## 4. `ensure_future` -> `create_task`

- [x] 4.1 Substitute `asyncio.ensure_future` with `asyncio.create_task` at
      `execution.py:159` and `execution.py:172`. One word at each site and
      nothing else — the surrounding `in_flight` dict, its comment and the
      re-arm logic are unchanged.
- [x] 4.2 Check the diff for this file is exactly two words. If it is not, the
      benchmark exemption has lapsed (design Decision 4): stop and run the
      established harness before continuing.
- [x] 4.3 Run the full suite, with the racing/parallel tests explicitly
      included — green, no test edited.
- [x] 4.4 Commit 4 of 4.

## 5. Close out

- [x] 5.1 Full validation matching CI: `uv run ruff check .`,
      `uv run ruff format --check .`, `uv run pytest`,
      `uv run pytest --cov-fail-under=98`, `uv run ty check src`.
- [x] 5.2 `openspec validate tidy-stream-chain-building --strict`.
- [x] 5.3 Confirm `git diff main --stat` touches only `stream.py`,
      `terminals.py`, `execution.py` and the planning artifacts — no `tests/`,
      no `README.md`.
- [x] 5.4 Move story 3 from **Now** to **Done** in `roadmap.md`, recording the
      cast removal (not in the original story text) and that the `create_task`
      exemption held. Update the **Now** preamble: the batch is down to
      stories 4, 5 and 6, and story 4 becomes next.
- [x] 5.5 Commit the roadmap update separately, then `/opsx:archive`.
