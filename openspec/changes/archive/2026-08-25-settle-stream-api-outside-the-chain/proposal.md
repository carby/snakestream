## Why

Three of `stream.py`'s methods that sit *outside* the op chain — `iterate()`,
`concat()` and `close()` — each drop something on the floor. `Stream.iterate()`
is the one user-supplied callable in the library not routed through the
library's dispatch, so an `async def nxt` yields un-awaited coroutine objects
with no error raised; that is the only silent-wrong-answer in the 2026-08-25
review batch. `Stream.concat()` discards both operands' close handlers.
`close()` runs every handler but then discards every exception except the
first. This is story 2 of the 2026-08-25 batch, and the two callables it fixes
are the ones a user can hit without doing anything unusual.

## What Changes

- **`Stream.iterate(seed, nxt)` accepts an async `nxt`.** `nxt` is routed
  through the library's canonical dispatch shape (`is_async_callable` +
  one-time `isawaitable` safety net, classified once per stream rather than per
  element), the same as every other user-supplied callable. `_make_iterator`
  becomes an async generator. A sync `nxt` behaves exactly as it does today.
  This replaces the silent-wrong-answer with correct values; it is not a
  breaking change, because the only call shape whose result changes is one that
  was already producing garbage.
- **`Stream.concat(a, b)` carries both operands' close handlers.** The
  concatenated stream is constructed with `a`'s handlers followed by `b`'s, so
  `close()` on the result closes both inputs, matching Java's `Stream.concat`.
  Registration order within each operand is preserved.
- **`Stream.close()` stops discarding the later exceptions' detail.** Which
  exception is raised is unchanged — the first, per the existing spec and test.
  The remaining exceptions are attached to it as notes via
  `BaseException.add_note()`, so a traceback shows all of them. `add_note()` is
  3.11+, and this project supports 3.10, so on 3.10 the behaviour is exactly
  what ships today (first exception raised, no notes). See design.md.

Nothing here changes the op chain, composition, or execution mode.

## Capabilities

### New Capabilities
- `stream-iterate`: the contract of `Stream.iterate(seed, nxt)` — an infinite
  ordered sequential stream of `seed, nxt(seed), nxt(nxt(seed)), ...`, lazy in
  `nxt`, with `nxt` accepted in all four sync/async function/callable-object
  forms. No spec covers `iterate()` today; it is only mentioned in passing by
  `stream-concat`.

### Modified Capabilities
- `stream-concat`: ADDED requirement that the concatenated stream's close
  handlers are both operands' handlers, in order. The spec is currently silent
  on close handlers, so this is a clean addition rather than a change of rule.
- `stream-close-handling`: MODIFIED "close() invokes every registered close
  handler" — the rule that the *first* exception is raised is unchanged; the
  requirement gains that the other exceptions' detail SHALL be preserved on the
  raised exception where the interpreter supports it.

## Impact

- `src/snakestream/stream.py`: `iterate()` (+ its inner `_make_iterator`),
  `concat()`, `close()`. Three independent edits in one file.
- `src/snakestream/type.py`: `iterate`'s `nxt` moves from a bare
  `Callable[[T], T]` to the existing `Mapper[T, T]` alias, which already
  permits a sync or async implementation. No new alias is needed.
- Tests: new async-`nxt` cases in `tests/test_iterate.py`, a close-handler case
  in `tests/test_concat.py`, and an assertion on the preserved detail in
  `tests/test_close.py`. The existing
  `test_close_with_multiple_raising_handlers_runs_all_and_raises_first` must
  keep passing unmodified.
- `README.md`: the `iterate` row of the parity table notes async `nxt` support.
  No migration-log entry — no working call site has to change.
- CI: the 3.10 leg is the one that exercises the `add_note()` fallback path,
  and the coverage gate runs on 3.14, so the fallback branch needs a
  version-guarded test or a pragma. Called out in design.md.
