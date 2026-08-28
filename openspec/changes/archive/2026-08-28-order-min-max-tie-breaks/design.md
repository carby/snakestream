## Context

See proposal.md — Why. The one implementation fact this design turns on: the
racing executor already restores encounter order for delivery, through
`_split_point()`'s third clause, which returns `len(chain)` when the terminal
observes order and the pipeline is ordered at the end of the chain. A split at
`len(chain)` leaves every operation racing and reorders only the handing of
finished elements to the terminal. `min()`/`max()` are the only terminals whose
result identity depends on order while declaring `observes_order=False`; every
other order-blind terminal (`count`, `for_each`, `find_any`, the `*_match`
family) has no result identity to depend on it.

## Goals / Non-Goals

**Goals**

- `Stream.min()`/`max()` reach the same tie-break as `collect(min_by())`/
  `max_by()` through the *same* mechanism, not a parallel one.
- `sorted()`'s stability becomes stated and tested, rather than an emergent
  property of Timsort that nothing pins down.

**Non-Goals**

- Cheapening the delivery barrier. The measurement below says where the cost
  sits; acting on it would change it for every order-observing terminal at once
  and is not this change's business.
- Revisiting whether `counting()`, `grouping_by()` and the rest should declare
  `UNORDERED` (roadmap item 4). This change removes `min_by`/`max_by` from that
  question permanently and leaves the remainder untouched.

## Decisions

### Use the existing delivery barrier, not a new mechanism

`_min_max()` flips its `observes_order` argument from `False` to `True`. That is
the whole implementation. Nothing in `execution.py` changes: no new executor, no
third gear in `race_through()`, no change to the `Executor` protocol, no second
sink protocol.

**Alternative considered: tag elements with a source index and tie-break on it,
without a reorder barrier.** Each branch would run `group_through()` over
`_guarded(shared, lock, window)` — which already yields `(index, element)` —
merge with `FIRST_COMPLETED` as the unordered path does today, and let the
terminal break ties on `(index, position_in_group)`. Nothing is held, so there
is no head-of-line blocking and no read-ahead bound is needed. It gives the same
semantics as the chosen approach.

Measured on the barrier's own shape (20,000 elements, `map(x + 1)`, 4 workers,
Python 3.14.5, best of 5, all three draining into the same counting sink):

```
  baseline (unordered)      7.32 us/element   stream_through + plain merge
  tagged, unmerged          8.03 us/element   group_through  + plain merge      +9.7%
  reorder barrier           8.71 us/element   group_through  + _release_in_order +19%
```

So the tagging half is 0.71 us/element and the reordering half 0.68 — the
barrier is almost exactly 50/50, and the alternative recovers 49% of it. It
cannot recover more: the chain drops (`filter`) and multiplies (`flat_map`), so
a per-element tag has no answer and `group_through()` is unavoidable, which is
the half it keeps. On the shape racing exists for it recovers nothing at all,
because the barrier is already free there (105.5 vs 106.9 ms on 40 elements at
10ms, per `race_through()`'s docstring) and the alternative is bounded between
that and the unordered baseline.

Rejected on what it costs to hold: a parameter on `Executor.value()`/
`elements()` threaded through both executors, because `elements()` also serves
`iterator()` and must keep yielding bare elements; a `bounded` flag on
`_Window`; a third branch in `race_through()`; a tagged terminal sink; and a
fork of `is_new_extremum()`, which both `comparator.py`'s docstring and
`collectors.py`'s comment call the one home for this rule. It would also have to
be built twice — `_CollectorSink` reaches the terminal by the same path, so
`min_by`/`max_by` would either need the tagged protocol again or stay on the
barrier, reintroducing the divergence this change exists to close. Half a
barrier on chains too cheap to race is not worth that.

### Ties stay unspecified on an unordered pipeline

Matching Java, and falling out of the mechanism for free: `is_ordered()` is
False there, so `_split_point()` returns `None` and no barrier is engaged.
Specifying it as unspecified is honest rather than a concession — `unordered()`
is the caller declaring any answer will do, and `then_comparing()` (landed
2026-08-28) now gives a caller who wants determinism a way to get it from the
data rather than from position, which is the better answer anyway.

### `sorted()`'s stability is stated in `comparator-contract`, not `stream-ordering`

Stability is what happens to *tied* elements, which is the question
`comparator-contract` already owns for `min()`/`max()`. Stating it there keeps
one capability answering "what happens on a tie" for all three
comparator-consuming operations. `stream-ordering` owns where the ordering
characteristic comes from, which is a different question.

The property holds today and needs no code: `_SortedOp` declares
`Ordering.SET`, `_split_point()`'s first clause fires on that unconditionally,
and all three sort algorithms are stable — `list.sort(key=cmp_to_key(...))` is
Timsort, `_sort_by_key()` sorts on keys alone (and `reverse=True` is stable in
the strong sense), and `merge_sort()`'s `_merge()` takes from the left half on
`sign <= 0`.

## Risks / Trade-offs

- **A racing `min()`/`max()` on a chain too cheap to race gets ~19% slower.** →
  Accepted, and documented. The barrier is free on work worth racing; the
  regression lands only where `.parallel()` was the wrong call. `unordered()`
  restores the old cost and the old semantics exactly, and is named in the spec
  as the lever.
- **The break is silent** — no exception marks an unmigrated call site, because
  the value only changes for callers who were relying on an arbitrary tie. →
  Mitigated by direction: the new answer is the sequential one, so a caller who
  compared the two modes now agrees where they previously did not. Migration-log
  entry required.
- **`racing-encounter-order` currently states that on an unordered pipeline "a
  sort's output carries no cross-branch ordering guarantee", which the
  implementation has never done.** → Corrected in this change's delta. Found
  while checking stability; it is a spec bug, not a code bug, and no behaviour
  changes.
- **The `min_by`/`max_by` requirement constrains a future change** (roadmap item
  4's marking pass). → Intended. It is written as an exclusion with a reason so
  that pass has one fewer thing to weigh.

## Migration Plan

No staged rollout. One argument changes; the specs and README land with it.
Rollback is the same argument.

The README rows to update: `max()`, `min()`, and the `parallel()` row, which
currently lists `max()`/`min()` among the terminals that "pay nothing either
way". A migration-log entry goes under the existing `0.3.5 -> next` block, which
already describes the delivery barrier this change extends to two more
terminals.
