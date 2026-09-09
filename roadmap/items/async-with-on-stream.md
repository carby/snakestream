+++
id = "async-with-on-stream"
title = "`async with` on `Stream`"
bucket = "now"
rank = 1
filed = 2026-08-31
updated = 2026-09-09
gate = "verify: async-close-handlers implemented the capability delta (widened `CloseHandler`, `aclose()`, `__aenter__`/`__aexit__`) and the source-slot unwrap it required; confirm on archive that the roadmap's guiding principle (no silent divergence in observable API behaviour) held before closing this item"

[refs]
changes = ["implement-python-data-model", "async-close-handlers"]
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

**Scaffolded 2026-09-09 as `async-close-handlers`.** Not split: the
source-slot question below turned out to be one piece of the same delta, not a
separate item. The original framing treated `Stream(other_stream)` as an
untested but *working* case that `aclose()` would make silently divergent
(`_maybe_aclose()`'s probe cascading into an inner stream's handlers). Task 1.1
found the actual current behaviour is a construction-time crash instead:
`Stream.__init__` builds `_accept(source) or _normalize(source)`, and `or`
forces a truthiness check on the `Stream` `_accept()` returns unmodified —
`Stream.__bool__` raises by design, so `Stream(other_stream)` already raises
`TypeError` today, before any handler cascade is reachable. The fix design.md's
decision 3 already specifies — unwrapping a `Stream` source to
`source.iterator()` in `_accept()` — resolves both: the crash, and the
handler-cascade risk the decision was written to prevent. No design change
followed from the correction, only a corrected premise (see design.md's
"Correction found during task 1.1" and tasks.md group 1/6).
