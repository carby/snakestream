+++
id = "what-counts-as-a-source"
title = "Settled what counts as a source, and how a racing branch consumes one"
filed = 2026-08-25
closed = 2026-08-25
outcome = "shipped"
+++

**Settled what counts as a source, and how a racing branch consumes one**
(2026-08-25). Story 1 of the 2026-08-25 batch, and the only crash in it.

**(a)** `.parallel()` raised `AttributeError` on any source the sequential
path accepts but that is not a full async generator: `_guarded()` called
`await source.aclose()` unconditionally and pulled with
`source.__anext__()`, while `_accept()` admits any `AsyncIterable`. Both
halves fixed — `race_through()` now calls `aiter(source)` **once** for all
branches, and `_guarded()`'s `finally` closes only if the source is
closeable.

**The trap worth recording:** the obvious placement for `aiter()` is the
first line of `_guarded()`, and it is silently wrong. `_guarded()` runs once
per branch, so a source whose `__aiter__` hands back a fresh iterator would
give each branch its own and yield the elements `PROCESSES` times over — a
wrong answer strictly worse than the crash it replaces. The
`__aiter__`-returns-a-separate-iterator test asserts the exact multiset for
this reason, and was confirmed to fail against the per-branch placement
before being accepted.

**(b)** `_accept()` collapsed to one `isinstance(source, AsyncIterable)` —
`AsyncGenerator` is a subclass of it, so the narrower arm could never
decide. **(c)** `_normalize()`'s `hasattr(source, "__iter__")` became
`isinstance(source, Iterable)`.

**Deliberately not done, and now recorded in the code rather than here:**
the neighbouring `hasattr(source, "__next__")` branch stays a `hasattr`.
`Iterator`'s `__subclasshook__` requires *both* dunders, so an object with
only `__next__` is neither `Iterable` nor `Iterator`; converting it would
reintroduce the bug fixed at `3554cc1` and break
`stream-construction`'s "Iterator source exposing only `__next__`"
scenario. The comment on that branch now says so, so the tidier-looking
conversion cannot be re-proposed as an oversight.

**(d) was the open decision, and it went to consistency:** `bytearray` and
`memoryview` are now scalar sources alongside `dict`/`str`/`bytes`.
`Stream.of(bytearray(b"ab"))` yields the one `bytearray`, not `[97, 98]`.
`bytes` was already scalar, so the mutable buffer and the view over a buffer
were spreading while the immutable buffer of the same data was not. This
**breaks silently** — results change, nothing raises — so it carries a
README migration-log entry. The `memoryview` half is a genuine judgement
call rather than pure consistency, since a `memoryview` cast to a non-byte
format has meaningful per-item iteration; spreading stays available as
`Stream.of(*mv)`.

One implementation detail beyond the plan: `_maybe_aclosing()`'s conditional
close was split into a `_maybe_aclose()` coroutine that both it and
`_guarded()` call. The context-manager form cannot hold the shared lock
across its own exit, and `_guarded()` must close under that lock, so
reusing the helper as-is was not available — the split keeps one definition
of "close if closeable" rather than duplicating the check.

546 tests green (536 + 10 new), **no existing test edited** — both test
files are pure additions. `ruff`, `ruff format --check`, `ty check src` and
`openspec validate --strict` all pass, 98% coverage. No benchmark gate:
every site runs once per stream construction or once per racing branch,
never per element. Spec impact: `stream-construction`'s scalar and
spreading requirements MODIFIED, and a new
"Source acceptance does not depend on execution mode" requirement ADDED to
`stream-execution-model` — the gap the crash fell through. See
`openspec/changes/define-and-guard-stream-sources`.
