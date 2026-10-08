+++
id = "concat-drops-async"
title = "Dropped the pointless `async` on `Stream.concat`"
filed = 2026-08-21
closed = 2026-08-21
outcome = "shipped"
+++

**Dropped the pointless `async` on `Stream.concat`.** `concat` was an
`async def` whose body never awaited anything — it built `_concat(a, b)`, an
async generator (so *calling* it runs none of its body), and wrapped it in a
`Stream`. The `async` bought nothing and cost every caller an `await` that
could not suspend, plus the requirement to be inside a coroutine to call it
at all. It is now a plain `def`, matching the other four static factories
(`of`, `empty`, `builder`, `iterate`) and Java's static `Stream.concat`.

**The one real decision was clean break vs. compatibility shim.** A `Stream`
subclass with `__await__` returning itself would have kept both call forms
working through a deprecation window; rejected because it puts an
`__await__` on a `Stream` either permanently or until a *second* breaking
change removes it, making the type worse than the one being fixed. The
project's pre-1.0 convention is a hard break plus a migration-log line
(`stream_of()` -> `Stream.of()`, the `Stream.of()` kwargs removal, the
`str`/`bytes` change), and that is what this took. No custom error either:
an unmigrated call site raises `TypeError: object Stream can't be used in
'await' expression`, which names the exact expression at fault, and a bespoke
`StreamBuildException` would have needed the rejected `__await__` to raise
from.

Scope stayed at one line of `src/`: `_concat`, the generator bridge, and the
`_consumed` bookkeeping are all untouched, so `concat` still leaves both
input streams unconsumed. A variadic `concat(*streams)` was named a non-goal
rather than left open — Java's is two-arg. Seven tests added in
`tests/test_concat.py` on top of the two existing ones dropping their
`await`: returns a `Stream` rather than a coroutine, `await` on the result
raises `TypeError`, callable from plain sync code with no running loop,
empty input on either side, and both laziness properties checked through
`peek` (nothing pulled at construction; the second stream untouched while
the first is being consumed). Those last two codify behaviour that was
already true — worth pinning precisely because the removed `async` is what a
reader might mistake for the source of the laziness.

Also corrected by omission: README's API table row for `concat` already
listed the return type as `Stream` while sibling rows mark awaitables
explicitly (`collect` reads `R (awaited)`), so the row was wrong before this
change and is right now — no edit needed. New spec capability
`stream-concat`; nothing in `openspec/specs/` covered `concat`'s own
behaviour before, only `terminal-sinks`' note that it composes through the
generator bridge, which still holds verbatim. 512 tests green, coverage
98.20%. See
`openspec/changes/archive/2026-08-21-drop-async-on-concat`.
