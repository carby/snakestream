## Context

See proposal.md — **Why**. The constraints that shape the approach:

- `sort()` recognizes a `KeyComparator` and takes the decorate-sort-undecorate
  path in `_sort_by_key()`: one column per segment, columns zipped into per-
  element tuples, one Timsort in C, three direction lanes (all-ascending,
  all-descending via `reverse=True`, mixed via `_Descending`). Anything that is
  not a `KeyComparator` falls to `cmp_to_key` (sync) or `merge_sort` (async).
- `Segment` is `(KeyExtractor, descending)` and `KeyComparator` holds a tuple of
  them. `reversed()` flips every segment's direction rather than negating
  `__call__`'s result, which is what makes reverse-before-chaining and
  reverse-after-chaining differ correctly with one implementation.
- `comparator-comparing` already requires that the sorting path and the
  `__call__` path (`min`/`max`/`min_by`/`max_by`) impose the same ordering.
- The `sort.py` / `comparator.py` split, settled by
  `split-sort-into-comparator-and-sort`: comparator *semantics* live in
  `comparator.py`, the sorting *algorithm* in `sort.py`.

## Goals / Non-Goals

**Goals:**

- Null tolerance that keeps `sorted()` on the existing C fast path rather than
  demoting a chain to `cmp_to_key` the moment it tolerates `None`.
- One rule that covers a null element and a null key, since a caller sees one
  symptom.
- No new direction lane, no new sort pass, no second ordering implementation.

**Non-Goals:**

- Roadmap gap 4 (`then_comparing(Comparator)`) and the two declined
  `keyComparator` overloads. They are blocked on the sync/async asymmetry
  recorded in `add-comparator-chaining/design.md` and moved to **Later** on
  2026-09-01. Nothing here touches that; see Decision 5.
- Tolerating anything other than `None` — no general "missing value" sentinel,
  no `NaN` handling.
- Making natural-order `sorted()` null-tolerant by default. Tolerance is opt-in
  per comparator; a bare `sorted()` over a stream containing `None` keeps
  raising `TypeError`.

## Decisions

### 1. Null placement is a property of the comparator, not of each segment

`KeyComparator` gains one field recording null placement — absent, first, or
last — rather than widening `Segment` to `(extractor, descending, nulls)`. Java's
`nullsFirst` wraps a whole `Comparator`, so a comparator-level field is the
shape that matches the API being ported; a per-segment field would be a knob the
public surface has no way to set independently, since `nulls_first()` takes a
comparator and not a segment.

`then_comparing()` carries the field onto the result, so a tie-break segment
appended to a tolerant chain is tolerant too. This is a deliberate divergence
from Java, where `nullsFirst(comparing(a)).thenComparing(b)` calls `b` on the
null elements `a` already ordered — two nulls compare equal under `c1`, so `c2`
sees them — and throws `NullPointerException`. Inheriting the field is the only
composition rule under which the spec's "a null key falls through to the
tie-break segment" scenario terminates.

*Alternative considered:* per-segment tolerance, set by a `nulls` argument on
`comparing()`/`then_comparing()`. Rejected: it invents surface Java does not
have, and the roadmap's guiding principle is 1:1 on the public API with freedom
only *underneath*. If a per-segment need appears later, the field can be widened
without changing what `nulls_first()` means.

### 2. A null element becomes a null key in every column, so there is no synthetic guard column

`_column()` yields `None` for a `None` element instead of invoking the extractor
on it — which also satisfies the spec's "the key extractor is never invoked with
`None`". A null element therefore presents as a null key in *every* segment, and
needs no leading guard column of its own.

This matters more than it looks. The obvious alternative is a synthetic
segment-zero holding "is this element null", ahead of the real segments. That
column would need a direction of its own for `reversed()` to move element-nulls
to the other end (Java's `nullsFirst(c).reversed()` puts nulls last), which means
a fourth thing for the three direction lanes to agree about, and a tuple
component every tolerant sort pays for whether or not any element is `None`.
Degrading the element case into the key case removes all of that: two `None`
elements compare equal on every segment and fall out in encounter order by
Timsort's stability, exactly as two elements with equal keys already do.

### 3. A tolerant column is `(present, key)`, and direction alone moves the nulls

A tolerant segment's column holds `(0, None)` for a null and `(1, key)` for a
non-null under nulls-first, and the two constants swap under nulls-last. Tuple
comparison settles a null-vs-null pair on the leading component and returns
before evaluating `None < None`, which is what makes this work at all —
confirmed against CPython: `sorted([(1,'b'), (0,None), (1,'a'), (0,None)])`
yields `[(0,None), (0,None), (1,'a'), (1,'b')]`.

`reversed()` then needs no null-specific rule. It already flips every segment's
direction, and flipping a column's direction reverses its `(present, key)`
tuples, which moves that column's nulls to the other end — so Java's
`nullsFirst(c).reversed() == nullsLast(c)` falls out of the mechanism that
already produces reverse-before/reverse-after. All three existing lanes carry
it: `reverse=True` reverses tuple keys, and `_Descending.__lt__` compares them
with `<`, which tuples support.

Presence is tested with `is None`, never truthiness: `0`, `False` and `""` are
keys, not nulls.

### 4. `nulls_first`/`nulls_last` dispatch on their argument, as `then_comparing()` already does

- Given a `KeyComparator`: return a new `KeyComparator` with the field set —
  fast path preserved.
- Given any other `Comparator`: return a plain wrapping comparator that checks
  for `None` and delegates otherwise. This is the Java behaviour and it sorts via
  `cmp_to_key`/`merge_sort` like any hand-written comparator, because there are
  no keys to build a column from. Sync or async is classified once at
  construction via `is_async_callable`, per `callable-dispatch`; an async wrapped
  comparator produces an async wrapper.
- Given nothing: as Java's `nullsFirst(null)` — nulls to their end, all
  non-nulls equivalent. Returned as a `KeyComparator` over a constant key, so
  even the degenerate form keeps the fast path and composes with
  `then_comparing()`.

Both return a new value and never mutate the receiver, per
`comparator-chaining`'s existing requirement.

*Alternative considered:* always return a plain wrapping comparator, matching
Java's return type exactly. Rejected on the fast path: `nulls_first(comparing(f))`
would sort slower than `comparing(f)` with nothing telling the caller why, and
silently losing an optimization at the moment a caller reaches for a
correctness fix is the worst place to put a cliff.

### 5. This does not reopen the comparator-segment question

The blocker recorded in `add-comparator-chaining/design.md` is that
`cmp_to_key` can fold a *sync* comparator segment into the tuple and cannot fold
an async one, and that asymmetry is what the decline bought off. Null tolerance
needs none of it: `(present, key)` is a transform on a key that a key extractor
already produced. So gap 5 ships without touching gap 4's premise, and gap 4
stays blocked on exactly what it was blocked on before.

### 6. Placement of the new code follows the existing split

The two factories and the placement field live in `comparator.py`, beside
`comparing()` and `Segment`; the `(present, key)` column lane lives in
`sort.py`'s `_column()`/`_sort_by_key()`. The placement enum stays in
`comparator.py` rather than `type.py` for the reason `add-comparator-chaining`
kept `KeyComparator` there: `type.py` holds callable aliases and protocols, and
this is neither.

## Risks / Trade-offs

- **A tolerant single-segment sort loses today's plain-key lane.** Its column
  becomes tuples, so the one-segment case that `add-comparator-comparing`
  measured now pays a tuple comparison. → Bounded and opt-in: only a comparator
  built by `nulls_first`/`nulls_last` builds a tolerant column, and every
  existing call reaches exactly the code it reaches today. Worth measuring, not
  worth avoiding — the alternative is raising `TypeError`.
- **The fast path and `__call__` could disagree about nulls.** The same drift
  risk `add-comparator-comparing` and `add-comparator-chaining` both carried,
  now over `None` as well. → Tests must assert the two agree across the matrix:
  first/last, reversed and not, chained and not, null element and null key, and
  on ties. The spec's last requirement exists to force this.
- **Inheriting tolerance through `then_comparing()` diverges from Java.** A
  caller porting Java code gets a terminating sort where Java throws. →
  Divergence in Java's favour is not available here (there is nothing to throw
  that would be more useful than an order), it is recorded in Decision 1, and it
  is invisible to any caller not sorting nulls.
- **A non-null key that cannot be compared with another non-null key still
  raises `TypeError`.** → Correct and unchanged; null tolerance is about `None`,
  not about heterogeneous keys. Stated in the spec's scope by omission.

## Migration Plan

Not breaking; nothing that sorts today sorts differently. Inputs that reach the
new behaviour raise `TypeError` today, so there is no prior behaviour to
preserve. A README Migration-log entry lands in the same commit as the change,
per project rule, recorded as not breaking.

## Open Questions

- What the tolerant single-segment lane actually costs against the plain-key
  lane. Settled by measurement during implementation, as `_column()`'s
  gather-vs-loop question was in `add-comparator-chaining`; the figure belongs in
  the docstring. It cannot change the specs or the approach — there is no
  cheaper representation on offer — only what the docstring claims.
