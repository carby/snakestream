+++
id = "async-with-on-stream"
title = "`async with` on `Stream`"
bucket = "later"
rank = 1
filed = 2026-08-31
blocked_on = "whether `close()` becomes awaitable, or grows an async twin — a change to the close-handler contract every subclassed resource wrapper depends on"

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
