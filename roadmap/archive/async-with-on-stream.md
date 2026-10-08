+++
id = "async-with-on-stream"
title = "`async with` on `Stream`"
filed = 2026-08-31
closed = 2026-09-09
outcome = "shipped"
shipped_as = "async-close-handlers"
+++

**`async with` on `Stream`** (closed 2026-09-09; filed 2026-08-31). Shipped as
`async-close-handlers`.

Parked out of the `implement-python-data-model` exploration, which implemented
the *synchronous* context manager and deliberately stopped there:
`CloseHandler` was a plain no-arg sync callable and `close()` invoked handlers
without awaiting, so `with` was the honest protocol for the contract as it
stood. Adding `__aenter__`/`__aexit__` would have been a claim that a handler
may be awaitable — a change to the `stream-close-handling` capability, not to
two methods — so the item sat waiting on that buy-in rather than on effort.

**The order the work was done in is the whole of why it was cheap.**
`CloseHandler` widened first to permit an awaitable result, `close()` stayed
synchronous and grew a refusal for what it cannot complete, `aclose()` became
the twin that awaits, and only then did the two dunders follow — from the
widened contract instead of claiming it. Nothing that subclasses `Stream` to
wrap a sync resource changed. The widening also put the close handler where
every other user-supplied callable in this library already was: a predicate,
mapper, comparator, consumer and accumulator each permit a sync or an async
implementation, and the close handler had been the lone exception.

**The item's own premise was wrong, and finding out cost one task.** It
treated `Stream(other_stream)` as an untested but *working* case that
`aclose()` would make silently divergent — `_maybe_aclose()`'s probe
cascading an outer stream's consumption into an inner stream's close
handlers. Task 1.1, run against unmodified `src/` precisely so it would pin
behaviour rather than describe it, found a construction-time crash instead:
`__init__` computed `_accept(source) or _normalize(source)`, and the `or`
forced a truthiness test on whatever `_accept()` returned unmodified, so
`Stream.__bool__` (which raises by design) fired before any handler cascade
was reachable. Worse, the same `or` silently mis-normalized any falsy
`AsyncIterable` — one with a zero `__len__` — into a single scalar element.
The fix the design had already specified for the cascade, unwrapping a
`Stream` source to `source.iterator()` in `_accept()`, resolved all three. No
design change followed from the correction, only a corrected premise. The
lesson is the sequencing rule, not the bug: a regression test written after
the change proves nothing about what the change preserved.

**The gate this item carried was a verification, and it caught something.**
Closing required confirming the roadmap's guiding principle — no silent
divergence in observable API behaviour — actually held. It held on the axis
that matters for parity: Java has no asynchronous close handler, and
`BaseStream.close()`'s contract (every handler runs, first exception wins,
the rest ride along) is preserved verbatim through the shared failure tail
both closers now use. What had slipped was the documentation half of the same
discipline. Two runtime behaviours changed without a Migration entry —
`close()` over an `async def` handler went from a silent no-op to a loud
refusal, and the falsy-`AsyncIterable` mis-normalization went from a wrong
answer to a right one — on the reasoning that the alias only widened and the
members were only additive. That reasoning is true of the *declared* contract
and not of the running code, and the Migration log's own stated standard is
that every breaking change gets an entry *regardless of how obscure*. Both
entries were written as a follow-up commit rather than by rewriting the
original, per this roadmap's fix-forward rule.
