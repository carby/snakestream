## Why

`CloseHandler` is a plain no-arg **sync** callable and `close()` invokes handlers
without awaiting, so a stream wrapping an async resource — the `DsnStream(dsn)`
shape `derive-without-reinit` made writable — has nowhere to put
`await conn.close()`. Every other user-supplied callable in this library
(`Predicate`, `Mapper`, `Consumer`, `Comparator`, `Accumulator`) already permits
either a sync or an async implementation; the close handler is the one that does
not, which is also why `Stream` implements `with` but not `async with`.

Roadmap Now item 1 (`roadmap/items/async-with-on-stream.md`), unblocked
2026-09-08. Its gate names the order: the capability delta comes first,
`__aenter__`/`__aexit__` follow from the widened contract rather than claiming
it.

## What Changes

- `CloseHandler` widens from `Callable[[], None]` to
  `Callable[[], Awaitable[None] | None]`, making it the nullary `Consumer` and
  removing the one alias in `type.py` that did not permit an async
  implementation. Strictly more is accepted, so no existing handler changes.
- `Stream` gains `aclose()`, an `async` twin of `close()`. It awaits an
  awaitable handler result and calls a sync handler exactly as `close()` does,
  in registration order, one at a time, under the same
  first-exception-propagates-with-later-ones-as-notes contract.
- `close()` stays synchronous and unchanged for sync handlers. Against a handler
  that would need awaiting it **refuses**: it raises rather than leaving an
  un-awaited coroutine behind, and the refusal joins the existing per-handler
  failure list, so every remaining handler still runs and the existing
  first-exception rule decides what propagates.
- `Stream` gains `__aenter__`/`__aexit__`, so `async with stream as s:` closes
  through `aclose()`. `contextlib.aclosing(stream)` starts working by
  construction, mirroring `contextlib.closing(stream)`.
- A `Stream` used as **another stream's source** still does not fire its close
  handlers on exhaustion. This is unchanged behaviour that only becomes
  load-bearing now: source teardown probes for an `aclose` attribute, which a
  `Stream` is about to have for an unrelated reason. Pinned as a requirement so
  it cannot regress silently.

Not breaking: the alias widens, the three new members are additive, and
`close()`'s behaviour over the handlers it accepts today is untouched. No README
Migration entry; the parity/data-model tables gain the new members.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `stream-close-handling`: the handler contract widens to permit an awaitable;
  `aclose()` is added with its ordering and failure semantics; `close()`'s
  refusal of an awaitable handler is specified; a stream consumed as another
  stream's source is pinned as not firing its handlers.
- `python-data-model`: the paragraph declaring the synchronous protocol the only
  one is replaced by a requirement that `Stream` is an asynchronous context
  manager too.

## Impact

- `src/snakestream/type.py` — the `CloseHandler` alias.
- `src/snakestream/stream.py` — `aclose()`, `__aenter__`/`__aexit__`, the
  refusal in `close()`, and the shared tail that decides which failure
  propagates.
- `src/snakestream/callable_dispatch.py` — reused, not changed:
  `is_async_callable()` decides the refusal before a handler is called;
  `isawaitable()` on the result is the after-the-fact net.
- `src/snakestream/execution.py` / `stream.py`'s `_accept()` — the source-slot
  question above; see design.md decision 3.
- `README.md` — the data-model and close-handling entries.
- `tests/` — new coverage for `aclose()`, the two dunders, the refusal, and the
  stream-as-source scenario.
