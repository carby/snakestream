+++
id = "stream-api-surface-outside-the-chain"
title = "Settled `stream.py`'s API surface outside the chain: `iterate`, `concat`, `close`"
filed = 2026-08-25
closed = 2026-08-25
outcome = "shipped"
+++

**Settled `stream.py`'s API surface outside the chain: `iterate`, `concat`,
`close`** (2026-08-25). Story 2 of the 2026-08-25 batch. Three independent
edits, one commit each, landed in order so a bisect lands on one behaviour.

**(a)** `Stream.iterate()`'s `nxt` was the one user-supplied callable in the
library not routed through the `is_async_callable`/`isawaitable` dispatch
shape every other callable uses — an `async def nxt` silently produced a
stream of un-awaited coroutine objects:

```python
async def nxt(x):
    return x + 1


await Stream.iterate(1, nxt).limit(3).to_array()
# [1, <coroutine object nxt>, <coroutine object nxt>]   -- no error raised
```

`_make_iterator` is now an `async def` generator carrying the same
`is_async`/`checked` locals as the canonical shape in
`callable_dispatch.py`, and `nxt`'s type moved from `Callable[[T], T]` to
the existing `Mapper[T, T]` — dispatched rather than pre-call-rejected
(the `flat_map` shape), since an async `nxt` is not structurally impossible
the way an async `flat_mapper` is, and rejection would still miss a
callable object with an async `__call__`. New capability spec
`stream-iterate`, covering the lazy seed/`nxt` sequence and all four
sync/async function/callable-object forms — nothing had specified
`iterate()`'s own contract before this.

**(b)** `Stream.concat(a, b)` built its result with an empty close-handler
list, discarding both operands' handlers. It now constructs the result with
`a._close_handlers + b._close_handlers` — a fresh list, so registering a
handler on either input after `concat()` returns does not retroactively
reach the result — matching Java's `Stream.concat`, whose result closes
both inputs. ADDED requirement on the `stream-concat` capability, a clean
spec gap rather than a rule change.

**(c)** `close()` collected every handler's exception but discarded every
one except the first. It still raises the first — that rule is unchanged,
pinned by the existing `test_close_with_multiple_raising_handlers_runs_all_and_raises_first`,
verified to pass unmodified — but now attaches the later exceptions to it
via `BaseException.add_note()` (Python 3.11+) in encounter order, so a
traceback shows all of them. On 3.10 the behaviour is exactly what shipped
before: first exception raised, no notes. `sys.version_info >= (3, 11)`
narrows for `ty` without a cast, which `hasattr(exc, "add_note")` would
not. MODIFIED requirement on `stream-close-handling`.

**Tripwire held exactly as scoped:** the only test files touched are
`tests/test_iterate.py`, `tests/test_concat.py` and `tests/test_close.py`,
and the pinned multi-raise test needed no edit. 561 tests green (536 + 25
new), `ruff`, `ruff format --check`, `ty check src` and
`openspec validate --strict` all pass, coverage 98.03%. No benchmark gate:
every site here runs once per stream, once per `concat()` call, or once
per `close()` call, never per element — story 4 is the batch's only
benchmark-gated story. README's `iterate` row now notes `nxt` may be sync
or async; no migration-log entry, since the only call shape whose result
changed was already producing garbage. See
`openspec/changes/settle-stream-api-outside-the-chain`.
