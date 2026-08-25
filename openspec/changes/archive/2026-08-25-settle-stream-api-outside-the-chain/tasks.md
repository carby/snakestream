## 1. Part (a) — `Stream.iterate()` dispatches `nxt`

- [x] 1.1 Turn `_make_iterator` (`stream.py:201`, inside `iterate()`) into an `async def` generator carrying the canonical dispatch shape from `callable_dispatch.py`'s comment block: `is_async = is_async_callable(nxt)` and `checked = False` as locals **inside the generator body**, `yield seed` first, then per iteration call `nxt`, await when `is_async`, and run the one-time `isawaitable` safety net when not yet `checked`.
- [x] 1.2 Change `iterate()`'s `nxt` annotation from `Callable[[T], T]` to `Mapper[T, T]` (already imported in `stream.py` — confirm, add to the import if not) and drop the now-unused `Generator` import if nothing else in the file uses it.
- [x] 1.3 Confirm the async-generator source reaches `_accept()` rather than `_normalize()` and that `Stream.of(single_arg)` still routes it through `Stream(args[0])` unchanged — no change should be needed in either, and needing one is a signal the shape is wrong.
- [x] 1.4 Add to `tests/test_iterate.py`: async-`def` `nxt`; sync callable object `nxt`; async-`__call__` callable object `nxt`; sync-signatured `nxt` returning a coroutine (this is the case that covers the `isawaitable` safety-net branch for the 98% gate). Each asserts the elements are values, not coroutine objects.
- [x] 1.5 Add to `tests/test_iterate.py`: laziness — `nxt` is not called when the stream is never consumed, and is called exactly `n - 1` times for `n` consumed elements. Assert via a counting `nxt`.
- [x] 1.6 Add to `tests/test_iterate.py`: `Stream.iterate(0, async_nxt).map(...).filter(...).limit(3)` matches the equivalent sync `nxt`, and `Stream.iterate(0, async_nxt).parallel().limit(10)` yields ten non-coroutine elements (design.md, Risks — this one proves the shared-source-under-lock combination works).
- [x] 1.7 Run `uv run pytest tests/test_iterate.py tests/test_limit.py tests/test_parallel.py`; the existing sync-`nxt` tests in all three must pass **unmodified**.

## 2. Part (b) — `Stream.concat()` carries both operands' close handlers

- [x] 2.1 In `Stream.concat()` (`stream.py:190`), pass `a._close_handlers + b._close_handlers` as the constructor's `close_handlers`. Use `+` (a fresh list), not extend-in-place or aliasing either operand's list.
- [x] 2.2 Add to `tests/test_concat.py`: both inputs' handlers run; order is `a`'s handlers then `b`'s, using **two handlers per side** so the ordering assertion cannot pass by accident; one side with no handlers; neither side with handlers.
- [x] 2.3 Add to `tests/test_concat.py`: a handler registered on `a` *after* `Stream.concat(a, b)` returns is not invoked by the concatenated stream's `close()`.
- [x] 2.4 Add to `tests/test_concat.py`: a raising handler on `a` does not prevent `b`'s handler from running, and `a`'s exception is raised after both have run.
- [x] 2.5 Run `uv run pytest tests/test_concat.py tests/test_close.py`.

## 3. Part (c) — `Stream.close()` preserves the later exceptions

- [x] 3.1 In `Stream.close()` (`stream.py:166`), keep collecting every handler exception and keep `raise exceptions[0]`. Before raising, when `sys.version_info >= (3, 11)`, `add_note()` one note per exception in `exceptions[1:]`, in encounter order, each identifying that exception. Add the `sys` import.
- [x] 3.2 Verify `tests/test_close.py:138-151` (`test_close_with_multiple_raising_handlers_runs_all_and_raises_first`) passes **unmodified** — this is the story's tripwire that the first-exception rule survived.
- [x] 3.3 Add to `tests/test_close.py`: three raising handlers → the first exception propagates and carries notes identifying the second and third, in that order. Guard the note assertion with `sys.version_info >= (3, 11)` (or `pytest.mark.skipif`) so the 3.10 leg passes.
- [x] 3.4 Add to `tests/test_close.py`: exactly one raising handler → the propagated exception carries no notes added by `close()`.
- [x] 3.5 Run `uv run pytest tests/test_close.py`.

## 4. Docs and spec sync

- [x] 4.1 Update the `iterate` row of README.md's parity table (`README.md:114`) to note that `nxt` may be sync or async, like every other user-supplied callable. Do **not** add a migration-log entry (design.md, Migration Plan).
- [x] 4.2 Re-read this change's three spec deltas against the implementation and confirm every scenario has a corresponding test; add any that is missing rather than trimming the spec.

## 5. Full validation

- [x] 5.1 `uv run ruff check .` and `uv run ruff format --check .`.
- [x] 5.2 `uv run ty check src` — in particular that the `sys.version_info` guard narrows without a cast (design.md, Decision 3).
- [x] 5.3 `uv run pytest` (full suite), then `uv run pytest --cov-fail-under=98`. If branch coverage flags the untaken `sys.version_info` edge on 3.14, mark that line `# pragma: no cover`, matching the spelling already used in `type.py` and `collector.py`.
- [x] 5.4 Confirm the only test files touched are `tests/test_iterate.py`, `tests/test_concat.py` and `tests/test_close.py`. A test edit anywhere else means the change went wider than the story (roadmap tripwire).
- [x] 5.5 `openspec validate settle-stream-api-outside-the-chain --strict`.
- [x] 5.6 Commit as three commits in order — (a) `iterate`, (b) `concat`, (c) `close` — so a bisect lands on one behaviour (design.md, Goals).

## 6. Roadmap

- [x] 6.1 Move story 2 out of the **Now** table in `roadmap.md` and into **Done**, following the shape story 1's entry already uses; leave stories 3-6 numbered as they are, per the roadmap's own note.
