+++
id = "async-with-on-stream"
title = "`async with` on `Stream`"
bucket = "now"
rank = 1
filed = 2026-08-31
updated = 2026-09-08
gate = "a delta to the `stream-close-handling` capability first — `CloseHandler` widened to permit an awaitable and `close()` given an async twin — with `__aenter__`/`__aexit__` following from it, not bolted on ahead of it"

[refs]
changes = ["implement-python-data-model"]
specs = ["stream-close-handling", "python-data-model"]
files = ["src/snakestream/stream.py", "src/snakestream/type.py"]
+++

Parked 2026-08-31, from the `implement-python-data-model` exploration. That
change implements the *synchronous* context manager (`__enter__`/`__exit__`) and
deliberately stops there. `CloseHandler` is a plain no-arg sync callable and
`close()` invokes handlers without awaiting, so `with` is the honest protocol
for the close-handler contract as it stands.

Adding `__aenter__`/`__aexit__` would be a claim that a handler may be
awaitable — a change to the `stream-close-handling` capability, not to the two
methods. It belongs in **Later** rather than **Now** because it needs the same
kind of buy-in the rest of this bucket does. Nothing blocks it; nothing yet
demands it either.

**Unblocked 2026-09-08: `close()` grows an async twin.** `CloseHandler` widens
to permit an awaitable and the sync `close()` stays as it is, so no existing
subclassed resource wrapper changes. `__aenter__`/`__aexit__` then follow from
the widened contract instead of claiming it. The capability delta to
`stream-close-handling` comes first; the two dunders are the consequence.
