## 1. Add the shared helper

- [x] 1.1 Add module-level `async def _copy_into(head: Sink[Any], src: AsyncGenerator, state_map: StateMap) -> None` to `src/snakestream/base_stream.py`, placed next to `_wrap_sink()` (the other module-level sink helper), holding the begin / cancellation-guard / `async for` accept-and-check / end sequence exactly as `design.md` spells it out.
- [x] 1.2 Move the `limit(0)` cancellation-guard comment from `_drive()` into `_copy_into()` verbatim, and give `_copy_into()` a one-line docstring citing Java's `AbstractPipeline.copyInto()`, matching how `_wrap_sink()` cites `wrapSink()`.
- [x] 1.3 Confirm `Sink` and `StateMap` are already imported in `base_stream.py` (they are, via the `snakestream.sink` and `snakestream.type` imports) and that no new import is needed.

## 2. Route the two terminal drives through it

- [x] 2.1 Rewrite `BaseStream._drive_to_sequential()` to `_check_not_consumed()`, `_wrap_sink(self._chain, terminal)`, then `async with _maybe_aclosing(self._stream) as src: await _copy_into(head, src, {})`, then `return terminal.result()`. Keep its existing docstring unchanged — the ordered/never-overridden contract it states is unaffected.
- [x] 2.2 Rewrite `ParallelStream._drive_to()` to `_check_not_consumed()`, then `async with _maybe_aclosing(self._compose()) as src: await _copy_into(terminal, src, {})`, then `return terminal.result()`. Keep its existing docstring — the "terminal sits outside the race" explanation still holds.
- [x] 2.3 Add `_copy_into` to `parallel_stream.py`'s existing `from snakestream.base_stream import _maybe_aclosing` line.
- [x] 2.4 Leave `BaseStream._drive()` alone: it keeps its own loop and both bridge-flush blocks, per `design.md` — "`_drive()`'s duplicated flush block stays". Do not route it through the helper and do not introduce a flush closure.

## 3. Verify behaviour is unchanged

- [x] 3.1 `uv run pytest` — full suite green with **no test file edited**. A required test edit means behaviour changed; stop and reassess rather than adjusting the test.
- [x] 3.2 `uv run pytest --cov-fail-under=98` — coverage at or above the pre-change figure. Record the before/after percentages.
- [x] 3.3 Pin the widened `_maybe_aclosing` scope in `ParallelStream._drive_to()`: confirm the existing tests covering `.parallel()` with `limit(0)` (and any other already-cancelled-at-begin terminal on a parallel stream) pass, and confirm by reading `_parallel()` that constructing `self._compose()` without ever pulling from it starts no task and leaves nothing pending. If no such parallel + `limit(0)` test exists, say so rather than adding one — adding tests is outside this change's scope, and 3.1's no-edit rule covers the rest.
- [x] 3.4 `uv run ruff check .`, `uv run ruff format --check .`, and `uv run ty check src` — all clean.

## 4. Confirm the shape of the diff

- [x] 4.1 `git diff --stat` shows exactly two files: `src/snakestream/base_stream.py` and `src/snakestream/parallel_stream.py` (plus `roadmap.md` from group 5). No test file, no `README.md`, no `stream.py`.
- [x] 4.2 Confirm every `_drive_to()` / `_drive_to_sequential()` call site in `stream.py` is untouched and unchanged in signature.
- [x] 4.3 Grep `src/` for the begin/guard/accept-loop/end sequence and confirm exactly two spellings remain: `_copy_into()` and `_drive()`. Confirm `tests/test_sink.py`'s local `_drive()` double is untouched, and that its comment still reads correctly against the new code (it mirrors the sequence, which now lives in `_copy_into()`; update only that comment's function reference if it names `BaseStream._drive()` specifically).

## 5. Record

- [x] 5.1 Move roadmap item 1 from **Now** to **Done** in `roadmap.md`, stating what landed (`_copy_into()` shared by the two terminal drives) and what was deliberately not done (the `_drive()` flush dedup), carrying the benchmark table from `design.md` so the rejection is on the record in the project's established rejection log.
- [x] 5.2 Renumber the remaining **Now** items and fix the bucket's dependency preamble, which currently says "Items 1 and 3 are independent of each other" and sequences item 4 behind items 1 and 2 — item 4(b) (`parallel_stream.py`'s `any([...])` and `tasks.index(task)`) was sequenced behind item 1 as "inside the loop item 1 rewrites", which is no longer true: this change does not touch `_parallel()`'s race loop. Restate 4(b)'s dependency accordingly.
- [x] 5.3 Confirm `README.md` needs no edit (every name involved is private and unexported, no parity table entry changes) and state that explicitly in the **Done** entry.

## 6. Folded in: document the `_compose()` seam

Added after group 5 at the user's request, on noticing that `_compose()` reads
as a pointless delegation to `_drive()`. It is not - it is the third member of
the dispatching/overridden family alongside `_drive_to` and
`_drive_to_sequential`, and the only one whose docstring was missing. Same
class of defect as the one this change fixes: reasoning that lives nowhere in
the code.

- [x] 6.1 Add a docstring to `BaseStream._compose()` stating that it is the dispatching form and the seam where execution mode is decided, and why `_drive()` cannot be that seam (`_parallel()` calls `_drive()` once per racing branch, so overriding it would make each branch fan out again).
- [x] 6.2 Add a one-line docstring to `ParallelStream._compose()` pointing back at it.
- [x] 6.3 Re-run group 3's checks unchanged: full suite green with no test edited, coverage at or above 98.21%, ruff and `ty` clean. Docstrings only - no statement changed, so any behavioural difference means something else is wrong.
