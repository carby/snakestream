## Context

See proposal.md - Why. The constraints that shape the approach, all of them
already true in the tree:

- **A comparator is never awaited.** `_reject_async_comparator` refuses an async
  supplied comparator at construction, and `sort.py`'s
  `_checked_segment_comparator` catches the one shape that lies about it. Only a
  key extractor can await. This is what makes the tail shareable across the sync
  and async paths at all.
- **`.segments` is a published internal contract.** `sort.py`'s
  `_segment_column()` reads it for the decorate-sort-undecorate fast path, so
  `sorted()` never enters `__call__`. Its shape must not move.
- **Everything else is private to one file.** No module in `src/` or `tests/`
  references `_norm`, the two sign twins, the two extract-pair twins, or
  `_compare_sync`/`_compare_async`.
- **Two behaviours are load-bearing and easy to lose while rearranging**, both
  established in `b1f5db2` and neither visible from the shape:
  `NullPlacement.ABSENT` must **not** pass `None` through (or `comparing(f)`
  silently sorts nulls last instead of raising out of the extractor), and the
  null check must run for a bare comparator segment (`extractor is None`), or a
  tie-break appended to a tolerant chain silently stops tolerating nulls,
  against `then_comparing()`'s documented rule.

The measurements this design rests on were taken on a scratch prototype against
a verbatim baseline and a byte-identical null test, 2000 pairs per sample,
order-balanced rotation, comparators built once per shape, min and median over
300-1000 rounds (WSL2). They are reproduced in `benchmark-findings.md`.

## Goals / Non-Goals

**Goals:**

- Move every per-comparison decision that is constant for the life of the
  comparator into `__init__`.
- Keep `KeyComparator`'s observable behaviour byte-for-byte identical, including
  which exception type surfaces from a contract violation and which end nulls
  sort to under every composition of `reversed()` and `then_comparing()`.
- Leave `.segments`, `sort.py` and the public factories untouched.

**Non-Goals:**

- **Reducing the tail to one copy.** It stays at two. See Decision 3.
- Changing `_NullsComparator`, which is already the same pattern one level
  simpler (`_is_async` classified once at construction).
- Optimizing construction. This design makes it slower on purpose (Decision 4).
- Touching `sorted()`'s column path, which is where the real sorting win already
  lives and which this cannot help.

## Decisions

### Decision 1: Specialize into closures at construction, not into subclasses or a dispatch table

A segment becomes a pair of closures built once: `extract`, the
`(a, b) -> (ea, eb)` half, and `compare`, the `(ea, eb) -> sign` half. The
per-comparison loop is then `extract`, `compare`, negate, short-circuit - two
calls and one branch, against the baseline's two-to-three calls and roughly six
constant tests.

*Alternatives considered.* **A `_Segment` class with `sign()`/`asign()`
methods** - rejected: an attribute lookup plus a bound-method call is not
cheaper than a closure call in CPython, and it would introduce a class
hierarchy this file has deliberately avoided (see the roadmap's guiding
principle: collectors are one `Collector` value rather than a hierarchy).
**Keeping the generic helpers and passing a pre-bound argument tuple** -
rejected: it removes argument marshalling but none of the branches, which the
measurements show are most of the sync-side win.

### Decision 2: The split is extract/compare, because that is where awaiting lives

`extract` is the only half that can await, so it is the only half with a
sync/async pair. `compare` is unconditionally sync and is therefore written
once and shared by both loops. This is the *structural* answer to the roadmap
item: the shared tail costs no extra frame because it replaces the
per-comparison `comparator is None` and `nulls is not ABSENT` tests rather than
sitting behind them.

The async loop keeps a per-segment `is_async` flag and calls a sync segment's
closure directly:

```
ea, eb = await extract(a, b) if is_async else extract(a, b)
```

*Alternative considered:* wrapping every sync extractor in a coroutine so the
async loop could `await` unconditionally. Rejected - it reintroduces exactly the
coroutine-that-awaits-nothing this change deletes, and the mixed-chain shape
(async segment + sync segment) is the largest measured win at -20.07%.

### Decision 3: The tail stays at two copies, on a different axis, and that is recorded rather than fixed

Natural ordering and the `type(sign) is not int` guard each appear twice, in
`compare_checked`/`compare_tolerant_checked` and the two natural-ordering forms.
The count is unchanged from the baseline's sync/async mirror. What changes is
the axis: from two copies 60 lines apart across an `async def` boundary, where
nothing but discipline keeps them in step, to two copies inside one builder
function, visible together.

Collapsing them further was measured and declined. Wrapping the intolerant leaf
in a tolerant one (`tolerant(inner, placement)`) costs the same frame the
roadmap item measured at ~10-19ns, on the tolerant path only, buying back
exactly what Decision 2 spent. The honest statement is that this change is a
performance change whose de-duplication is a side effect, not the reverse - the
roadmap item asked for the tail to be shared, and the answer is that it becomes
*shareable* (one `compare` half serving both loops) without becoming *singular*.

### Decision 4: Pay construction cost to buy per-comparison cost

Construction rises +388 to +910 ns per comparator (+10% to +52%), because the
closures are built there. Break-even is ~11 comparisons on a sync chain and ~5
on an async one. Every consumer of `__call__` - `min()`, `max()`, `min_by()`,
`max_by()` - performs n-1 comparisons over a stream, so a stream of a dozen
elements already pays it back and everything larger is pure win. A comparator
built and used for fewer than ~11 comparisons is slower than before; no such
call site exists in the library or its tests.

### Decision 5: Builders return `Any`, deliberately

`_build_extract` and `_build_compare` are annotated `-> Any`. `ty` passes clean
on the prototype - which is worth stating plainly, since the last prototype in
this file died on the type checker (`merge-segment-sign-on-natural-ordering`,
whose stated reason was later found not to hold). It passes partly *because*
`Any` leaves nothing to check, the same trick `_extract_pair_sync`'s docstring
already calls load-bearing. A precise `Callable[..., tuple[Any, Any]] |
Callable[..., Awaitable[tuple[Any, Any]]]` union was considered and rejected:
the loop would need a cast on every call to consume it, which is the cost this
change exists to remove.

## Risks / Trade-offs

- **Closures are harder to step through than named module functions.** → The
  four `compare` builders and four `extract` builders are given real names
  (`compare_tolerant_checked`, `extract_keyed_async`, ...) rather than being
  anonymous, so a traceback names the shape that raised. A user comparator's
  contract violation now surfaces a `compare_tolerant_checked` frame where it
  used to surface `_segment_sign_sync`.
- **The two load-bearing null behaviours are exactly what a rearrangement
  loses.** → `ABSENT`-does-not-pass-`None`-through becomes *structural*: no
  tolerant builder is reachable when `nulls is ABSENT`, so it cannot be lost by
  editing a condition. The bare-comparator-segment case is not structural and
  stays a test: a tolerant chain with a `then_comparing(comparator)` tie-break
  must still tolerate null elements.
- **`C901 _build_compare is too complex (11 > 10)`** on the prototype, the
  nested closures counting toward the enclosing function. → Split the two
  tolerant leaves into their own builder, or lift the four leaves to module
  scope as factories. Resolve during implementation; it is a shape question, not
  a redesign.
- **Regression risk is concentrated in behaviour no unit test names.** → The
  prototype was validated against a verbatim baseline across 26 shapes x 49
  input pairs before this change was proposed; that harness is the acceptance
  bar, on top of the existing suite.
- **The measured win is WSL2-only, one machine.** → The direction is
  mechanical rather than incidental - two coroutine allocations and ~six
  constant branches per segment per comparison are deleted, and every shape moves
  the same way - but the magnitudes should be treated as this machine's.

## Migration Plan

None required. No public API, no serialized state, no behaviour change; the
change is a single-file internal restructuring. Rollback is a revert.
