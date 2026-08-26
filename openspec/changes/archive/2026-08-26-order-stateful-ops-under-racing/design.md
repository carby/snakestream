## Context

See `proposal.md` — Why. The constraints that shape the approach, all read off
the current `execution.py`:

- Encounter order is knowable in exactly one place: inside `_guarded()`, under
  the shared `asyncio.Lock`, at the moment a branch wins a pull. That is the
  last point at which pull order still *is* encounter order.
- It is destroyed in exactly one place: the `asyncio.wait(FIRST_COMPLETED)`
  merge at the bottom of `race_through()`.
- Everything in between is per-branch and order-blind by construction — each
  branch owns its own sink chain, which is precisely why `Racing` inherits the
  generic `Executor.value()` rather than fusing a terminal onto one chain.
- `execution.py` may import `sink.py` but not `stream.py`; the dependency runs
  the other way. The ordering fold currently lives on `Stream` as
  `_is_ordered()` and is therefore not reachable from where the decision has to
  be made.
- `_SortedOp` is a `StatelessOp`; `_LimitOp`/`_SkipOp`/`_DistinctOp` are
  `StatefulOp`s whose shared state is delivered through `begin(state_map)`.
  None of the four sinks is wrong *in itself* — each is exactly right on a
  stream arriving in encounter order. The defect is that no such stream reaches
  them under racing.

## Goals / Non-Goals

**Goals:**

- One mechanism for all four operations, rather than four repairs. They fail for
  one reason and should be fixed at the one place the reason lives.
- Keep racing everything upstream of the first order-sensitive operation. The
  pipeline shape `RACING` exists for is `.map(fetch).limit(5)`; a fix that
  serialises the `fetch` fixes the wrong thing.
- Bounded memory. Ordering without a bound is a memory leak wearing a
  correctness hat.
- Leave the unordered path byte-for-byte on today's code, at today's cost.
- Leave the two-operation `Executor` protocol untouched.

**Non-Goals:**

- A parallel merge sort. Java's `SortedOps` + `Nodes` decomposition assumes
  partitioned leaves; this design has one shared source and no partitioning.
  The sort here buffers and sorts once, downstream of the barrier.
- Racing `find_first()` / `for_each_ordered()`. The barrier makes it possible
  and collapses four special cases into one; it is a separate change.
- Any change to `Stream`'s public surface, or a third executor.

## Decisions

### 1. Split the chain at the first order-sensitive operation; race the head, order the tail

`race_through()` finds the index `i` of the first operation that needs encounter
order. Operations before `i` race across branches exactly as today. At the merge,
a reorder buffer releases in encounter order. Operations from `i` onward run as
one sequential sink chain over that ordered stream.

`.map(fetch).limit(5)` therefore races the `fetch` across all branches and picks
the first five in encounter order — the concurrency is kept where the cost is.

*Alternative rejected: force the whole pipeline `SEQUENTIAL`* (the roadmap's
first suggestion, "the way `for_each_ordered()` does"). One line, correct, and
it deletes the concurrency in exactly the case the caller reached for
`.parallel()` to get. It also permanently forecloses the test debt: a sort under
`RACING` would stay indistinguishable from an unordered one, so the third
mutation row — nothing behavioural notices when `sorted()` stops restoring
encounter order — could never be closed. That argument stands independent of
performance and is the stronger of the two.

*Alternative rejected: segment without a reorder point*, running everything
downstream of the barrier sequentially but merging out of order. It does not fix
anything: `limit(5)` downstream of an unordered merge still picks the wrong five.

**Amended during implementation:** "operations from `i` onward run as one
sequential sink chain" is right only up to the point the caller clears the
characteristic again. `.sorted(c).unordered().map(fetch)` splits at the sort, so
a wholly sequential tail serialises the very `fetch` that `unordered()` exists
to release — and it makes `unordered()` after a barrier unobservable, which is
the observable the `stream-ordering` delta's fourth scenario and task 9.1 both
depend on. So the tail runs ordered up to the first op declaring
`Ordering.CLEAR` and hands the remainder back to `race_through()`, which may
split it again (`_resume_point()`).

Only an explicit clear resumes the race, not merely the absence of anything
downstream that reads position. Racing an order-blind *suffix* — the `map` in
`.limit(n).map(fetch)` — would scramble the order the pipeline delivers, and
whether an ordered racing pipeline owes its terminal encounter order is a
question this change does not answer: today it does not (`.parallel().map(f)`
comes out scrambled), Java's ordered parallel streams do, and this change makes
the answer depend on whether a barrier happens to exist. That is recorded as its
own roadmap item rather than settled here.

### 2. The split rule: `Ordering.SET`, or order-sensitive at an ordered position

An operation is a split point when either:

- it sets the ordering characteristic (`sorted()`), regardless of the
  characteristic upstream of it; or
- it is order-sensitive (`limit`, `skip`, `distinct`) **and** the fold over
  `chain[:i]` reports the pipeline ordered at its position.

The first clause is load-bearing and not obvious. `.unordered().sorted()` is
*unordered at the sort's own position*, so the second clause alone would leave
the sort in the raced head, sorting each branch's subset — and then
`.unordered().sorted(asc).limit(3)` would split at the `limit` and take the
three smallest of a wrongly-merged sort. A sort claims its output is ordered;
it must therefore see the whole stream. Java reaches the same place from the
other side: `SortedOps` contributes `IS_ORDERED` downstream precisely because it
imposes an order its input need not have had.

The first split point wins; there is at most one barrier per composition.

### 3. Reorder by source-element group, not by tagged element

The merge cannot key on a per-element index, because the head chain does not
preserve one element per element: `filter` drops, `flat_map` multiplies. What
*is* invariant is the group — everything the head chain emits in response to
source element `k` — and encounter order for the head's output is exactly
"every output of group 0, then group 1, ...".

`_guarded()` assigns `k` under the lock as it hands the element on. The branch
runs its existing sink chain unchanged; the `GeneratorBridgeSink`'s buffer is
already flushed once per `accept()`, and that flush point *is* the group. The
branch yields `(k, outputs)` instead of yielding elements one at a time; the
merge holds groups in a dict keyed by `k` and releases while `next_k` is
present.

This is why no head sink needs to know about indices, and why `Op`/`Sink` are
untouched apart from one declaration.

*Alternative rejected: tag each element and carry the tag through the head
sinks.* It requires every sink to propagate a tag it has no use for, and it has
no answer for `flat_map` (one tag, many outputs) or `filter` (a tag with no
output, which the merge would wait on forever).

### 4. Bounded read-ahead, enforced where the index is assigned

The merge shares a small window object with `_guarded()`: the last released
group index, plus an `asyncio.Event`. Before competing for the lock, a branch
whose next index would exceed `last_released + W` awaits that event. The merge
bumps the index and sets the event on each release.

The check sits in `_guarded()` because that is already the only place a pull
happens and the only place the index exists — the bound costs no new
synchronisation point. It is the analogue of the leaf partitioning that bounds
Java's fork-join, which this design otherwise lacks.

Two details that matter:

- **The wait is outside the lock.** Waiting while holding it would stall every
  other branch's pull, including the branch holding the group the merge is
  waiting for. Wait, then acquire, then re-check.
- **It cannot deadlock.** A branch blocks only *before* pulling a new element —
  after its previous group has already been handed to the merge. So the group
  the merge is waiting for is either already delivered or in flight in a branch
  that is mid-processing and therefore not blocked. Holds for any `W >= 1`.

`W` is a module-level constant in `execution.py`, **not** exported. `PROCESSES`
is exported because it names a real Java-side concept and is spec'd; `W` names
an implementation bound with no Java counterpart, and the tuning lever the spec
does give the caller is `unordered()`. Revisit only on a concrete report.

### 5. The ordering fold moves to `sink.py`; `Stream._is_ordered()` delegates

`execution.py` needs the fold and cannot import `stream.py`. The fold is a
property of a list of `Op`s, and `sink.py` already owns `Op` and `Ordering` and
is already imported by both. So `is_ordered(chain)` becomes a module-level
function there, and `Stream._is_ordered()` becomes a one-line delegation.

The method stays. It is what keeps the characteristic off the public surface
(the decision `make-is-ordered-internal` settled) and what the four accessor
scenarios in the mode-switch requirement assert through. Moving the fold is a
relocation, not a re-litigation.

### 6. The `Executor` protocol does not change

The barrier lives entirely inside `race_through()`, which is `Racing.elements()`.
`Racing.value()` stays the inherited generic `drain(self.elements(...),
terminal)` and needs no knowledge of any of this. `Sequential` is untouched. The
`stream-execution-model` delta says this explicitly so a future reader does not
mistake the internal split for a third mode.

## Risks / Trade-offs

- **Head-of-line blocking.** If the first element is the slow one, nothing
  downstream of the barrier moves until it lands. → Inherent to encounter order,
  not to this design; Java pays it too. `unordered()` is the escape hatch, and
  this change is what makes it a real performance lever rather than a semantic
  footnote — which the `racing-encounter-order` spec now requires.

- **Over-pull upstream of a short-circuiting operation.** `.peek(fn).limit(5)`
  under an ordered racing pipeline may call `fn` more than five times, up to the
  window. → Bounded by `W`, spec'd as permitted, and already true of racing
  today. `pipeline-composition`'s exact-`n` no-over-pull guarantee is a
  sequential-executor guarantee and is unaffected.

- **Deadlock or a hung `aclose()` from the window backpressure.** → Argued
  deadlock-free in Decision 4; the wait is outside the lock, and
  `race_through()`'s existing `finally` cancels in-flight tasks. Needs a
  dedicated test with a source far longer than `W` and a first element far
  slower than the rest, plus one that closes the generator early mid-block.

- **Cancellation now crosses the barrier.** `limit`'s
  `cancellation_requested()` sits downstream of the merge, so it must still stop
  the upstream pull rather than merely stopping the tail. → The driving loop
  closing the merged generator triggers `race_through()`'s `finally`, which
  cancels the branches and closes the shared source. Pin it: an ordered racing
  `.limit(n)` over an infinite source must terminate.

- **A regression on the unordered path.** → The split search runs once per
  composition over a single-digit chain, and when it finds nothing
  `race_through()` takes today's code path unchanged. Benchmark the unordered
  racing path before and after and report the figures; a measurable per-element
  regression there is a blocker, not a footnote.

- **Memory under the window.** `W * workers` groups may be resident, and a group
  may be large if a `flat_map` sits in the head. → Accepted and documented; the
  spec bounds it in terms of the window, not absolutely, and exempts what an
  operation buffers by its own definition (`sorted()`).

## Migration Plan

No public API changes, so no caller migration. Behaviour changes only where it
was wrong — an ordered `RACING` pipeline containing `sorted`, `limit`, `skip` or
`distinct`. Ship as one change; rollback is a revert. `README.md`, `CLAUDE.md`
and `roadmap.md` all repeat the unconditional claim that racing does not
preserve encounter order; each must become conditional in the same change.

## Open Questions

- The value of `W`. It does not affect the specs, the approach or the task
  breakdown — only a constant. Pick a starting value tied to the worker count,
  measure the read-ahead/latency trade-off on the benchmark used above, and
  record the figures next to the constant the way `Sequential.value()`'s
  docstring records its own.
