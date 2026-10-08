+++
id = "collapse-compose-into-iterator"
title = "Collapse `Stream._compose()` into `iterator()`"
filed = 2026-08-27
closed = 2026-08-27
outcome = "shipped"
+++

**Collapse `Stream._compose()` into `iterator()`** (2026-08-27). `_compose()`
had shrunk, since the executor-value redesign, to a one-line forward to
`self._executor.elements(...)` — the only thing separating it from the
public `iterator()` was the `_check_not_consumed()` call `iterator()` makes
and `_compose()` skipped. That gap was reachable from user code in exactly
two of its four call sites: `Stream.concat()` and a `flat_map()` mapper's
return value could both slip an already-extended stream past the
pipeline-immutability contract. Deleted `_compose()` and routed all four
callers — `_concat()`, `_FlatMapSink.accept()`, `collect()`'s
`StreamingCollector` branch, and `iterator()` itself — through `iterator()`.
See `openspec/changes/archive/2026-08-27-collapse-compose-into-iterator`.

**BREAKING (behavioural, previously unspecified):** `Stream.concat()` and a
`flat_map()` mapper now raise `IllegalStateException` on an already-extended
argument. Neither was ever documented as accepting one, so no README
migration-log entry — the two newly-raising cases were unsupported
before this, just silently so. A stream that was merely *terminally
consumed*, never extended, is unaffected in both positions.

**`_concat()` moved the check out of its own body, not into it.** It is an
`async def` generator, so a `_check_not_consumed()` call inside it would not
run until first pull — a materially weaker guarantee than "raises when you
call `concat()`". `Stream.concat()` now calls `a.iterator()` / `b.iterator()`
itself before constructing `_concat(a.iterator(), b.iterator())`, which also
dropped `_concat()`'s only dependency on `Stream`: it takes two
`AsyncGenerator`s now, nothing else.

**Four specs touched, no guarantee changed except the one stated above.**
`pipeline-immutability` gained the argument-position scenarios;
`pipeline-composition`, `stream-iterator`, and `mutable-reduction-collect`
had prose restated from `_compose()` naming to the executor vocabulary they
already used elsewhere — a legibility fix, not a behaviour change.
`pipeline-composition`'s `## Purpose` named both `_compose()` and the
already-stale `_parallel()` (deleted by the executor-value redesign); hand-
edited at archive time, since a delta can't carry `## Purpose` for an
existing capability.
