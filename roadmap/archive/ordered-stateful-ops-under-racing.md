+++
id = "ordered-stateful-ops-under-racing"
title = "Ordered `sorted()`/`limit()`/`skip()`/`distinct()` under `RACING`"
filed = 2026-08-26
closed = 2026-08-26
outcome = "shipped"
+++

**Ordered `sorted()`/`limit()`/`skip()`/`distinct()` under `RACING`**
(2026-08-26). All four gave **wrong answers**, not slower ones, on an ordered
pipeline under the racing executor: `_LimitSink`/`_SkipSink` shared one
counter and `_DistinctSink` one set across branches, so all three implemented
Java's *unordered* behaviour unconditionally, while `_SortedOp` was a
`StatelessOp`, so each branch sorted its own subset and the merged output was
not sorted at all. `.map(slow).limit(5)` over `range(12)` returned
`[0, 1, 2, 3, 5]`; `.sorted(asc)` over an async `12..1` returned
`[4, 2, 3, 1, 8, 6, 7, 12, 5, 10, 11, 9]`. See
`openspec/changes/archive/2026-08-26-order-stateful-ops-under-racing`.

**One bug seen from four angles, so one mechanism rather than four repairs.**
A stateful op's decision depends on a global position its branch cannot see.
Encounter order is knowable in exactly one place — inside `_guarded()`, under
the shared lock, the last point at which pull order still *is* encounter
order — and destroyed in exactly one, the `FIRST_COMPLETED` merge. So
`_split_point()` finds the first op that either declares `Ordering.SET` or is
`order_sensitive` at a position the fold reports ordered; the head races as
ever, `_release_in_order()` restores order at the merge, and the tail runs as
one ordered pass.

**Reordering is by source-element *group*, not by tagged element.** A head
chain does not preserve one output per input — `filter` drops, `flat_map`
multiplies — so a per-element tag has no answer for either. The group does:
everything the head emits for source element `k`. `group_through()` yields
`(k, outputs)`, using the `GeneratorBridgeSink` buffer flush that already
happens once per `accept()` as the group boundary. That is why no head sink
learned about indices and `Op` gained exactly one declaration
(`order_sensitive`) rather than a protocol change.

**`unordered()` became a real performance lever.** On an unordered pipeline
no barrier is inserted and today's cheap path runs unchanged — measured, and
the ranges overlap: 20,000 elements, four workers, best of five over three
interleaved runs, `132-141ms` before against `138-143ms` after on an empty
chain and `152-157ms` against `152-159ms` on a three-op chain. On the ordered
path the concurrency the change exists for is kept: `.map(fetch).limit(5)`
with a 20ms fetch costs `102ms` sequential and `42ms` racing, with an
identical result.

**Read-ahead is bounded at `_READ_AHEAD = 16`, enforced in `_guarded()`**
where the index is assigned — already the only place a pull happens, so the
bound cost no new synchronisation point. The curve that picked it is in the
constant's own comment; the knee is at the worker count and everything past
it is a slow 20% tail that would be bought with unbounded over-pull upstream
of a short-circuiting op.

**What the design got wrong, and how.** Decision 1 said the whole tail runs
as one sequential sink chain. That serialises `.sorted(c).unordered().map(fetch)`
— the exact `fetch` `unordered()` exists to release — and, worse, leaves
`unordered()` after a barrier with no behavioural observable at all, which is
the observable the test debt below is repaid *through*. Corrected during
implementation: the tail runs ordered up to the first `Ordering.CLEAR` and
hands the remainder back to `race_through()` (`_resume_point()`). The
design doc carries the amendment inline rather than being rewritten, so the
original reasoning and its correction both stay readable.

**The test debt on the sort is repaid, which the roadmap made a condition of
the fix rather than a follow-up.** The four `sorted()`-restores tests in
`test_unordered.py` are behavioural, with the positional delay queued
*before* the sort so the branches really do split the source — without it a
sort that had stopped restoring the characteristic still passes by one branch
happening to take everything. `test_for_each_ordered.py`'s weak test is
repaired the same way, and it gained the missing pin on the `unordered()`
relaxation of `for_each_ordered()`. Re-running the three inversions: with
`_is_ordered()` forced `True`, **14** behavioural tests fail; forced `False`,
**26**; with `_SortedOp.ordering` set to `PRESERVE`, **8** — where before the
change that third inversion was caught by **none**, which is what made the
debt worth repaying here rather than later.

**One spec claim was written and then found false.** The
`racing-encounter-order` delta first said a closeable shared source "SHALL
still be closed exactly once". It is not, and never was: each branch's
`_guarded()` closes it on the way out, so a duck-typed `aclose()` sees one
call per worker, and only an async generator's `finally`-runs-once semantics
made it look like one. Restated to what holds and what this change actually
owes — that introducing a barrier does not change the count — with a scenario
pinning both halves. Worth remembering as a shape: a requirement asserting
today's behaviour is still a claim that has to be measured.
