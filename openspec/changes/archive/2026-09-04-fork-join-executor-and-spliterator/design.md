## Context

See `proposal.md` — Why. `add-free-threaded-ci-leg` is landed; this change is
what it was for.

**Measured against the real library**, not a synthetic harness: materialising
contiguous batches and running the actual `Stream` chain over each in a worker
thread with its own event loop gives **2.37x** (sync mapper) and **2.36x**
(async mapper) at 4 workers on 1000 elements, output identical to sequential,
encounter order preserved — including through `flat_map`, which changes
cardinality and so would expose any per-element index assumption.

Two constraints shape the mechanism:

1. **The source cannot be shared across event loops.** It is an
   `AsyncGenerator` bound to the loop that created it. A worker thread runs its
   own loop and cannot pull from it. Batches must therefore be *materialised* on
   the main loop and handed over as lists.
2. **That is what Java does too.** `Spliterators.IteratorSpliterator.trySplit()`
   drains a growing batch for exactly this reason — an unsized source cannot be
   index-split. So batching is faithful to Java's own unsized path rather than a
   Python workaround, which is the difference between a divergence and an
   implementation.

## Goals / Non-Goals

**Goals:**

- Java parity on `spliterator()`, implemented rather than shimmed.
- `.parallel()` that parallelises CPU-bound work, with its observable contract
  unchanged for an *ordered* pipeline. Narrowed in one specific way for an
  `unordered()` one - see decision 9, found during implementation.
- Delete the reorder-barrier apparatus. This is a first-class goal, not a
  side effect: it is the most intricate machinery in the package and it exists
  solely to repair damage the new decomposition never does.

**Non-Goals:**

- Combiners. `collect()`'s inert combiner and the three-argument `reduce()` are
  change 3, and this change is what unblocks them by supplying contiguous
  decomposition.
- Changing what `.parallel()` *means* to a caller on an ordered pipeline.
  Same elements, same order, same short-circuiting. `unordered()`'s own
  contract does narrow - decision 9.
- Tuning. Batch sizing gets a defensible default and a measurement, not a curve.

## Decisions

**1. Batch size is the single bound, replacing three mechanisms.**

Today in-flight work is bounded by `_IN_FLIGHT_PER_WORKER`, `_in_flight()` and
`_Window` together. Under fork/join, one number does it: a batch is pulled,
handed to a worker, and no further batch is started for that worker until it
returns. Read-ahead is therefore `workers × batch_size`, which is the same
quantity `_in_flight()` computed, expressed where it is already visible.

Java's `IteratorSpliterator` starts at 1024 and grows by 1024 per split. That
curve is for a fork-join pool splitting recursively; here the split is flat —
one batch per worker — so the growth has nothing to do. A fixed default is the
starting point and the measurement is a task, not an assumption.

**Made concrete, and flagged rather than left implicit** (a peer review during
implementation asked for this to be stated explicitly): steady state reuses
`spliterator.BATCH_SIZE` (1024) as the per-worker read-ahead too, not a
separate number chosen for this bound - `workers × BATCH_SIZE` is `4096` at
the defaults, against the old window's `16`. Every reason `_IN_FLIGHT_PER_WORKER`
existed - memory held resident, latency behind a straggler, wasted upstream
invocations under a short-circuiting terminal - still applies at 4096; nothing
about fork/join makes them go away. This is deliberate reuse, not oversight:
decision 1's own argument is one number for both jobs rather than two to keep
in sync. Task 7.2 is where it gets measured, and where a bound of its own for
this specific purpose - if the measurement calls for one - would be decided.
`_FIRST_BATCH_SIZE`, the first-round probe size, is `_IN_FLIGHT_PER_WORKER`
itself (4) rather than the old window's *total* (`_in_flight(workers)` = 16) -
`_pull_round()` already multiplies by `workers` once, so reusing the total
there double-counted it (a bug the same review caught: round 1 was pulling 64
elements, not 16, before this was fixed).

*Why 4096 costs less than it looks like it does, on reflection* (same review,
a follow-up once the numbers above were verified independently): two of the
three jobs `_IN_FLIGHT_PER_WORKER` did barely reach steady state at all. The
speculative-invocation cost - `filter`/`flat_map` running a chain callable on
elements a short-circuiting terminal never needed - is a round-1 concern:
`limit(3)`, `find_first()` and a `limit()` barrier all settle inside the
first `_FIRST_BATCH_SIZE`-per-worker probe and never reach the growth to
`BATCH_SIZE`. Straggler latency is what the order-blind-terminal exception
above already names and bounds explicitly. What's left genuinely live at
4096 is memory on a pipeline that *drains* - and there, over-pull is free by
definition, since every element gets processed regardless. That is the
weakest of the three original reasons, and exactly what task 7.2 should
measure rather than a plan should guess at.

*For task 7.2, not decided here:* growth is currently one step, `_FIRST_
BATCH_SIZE` straight to `BATCH_SIZE` (a 256x jump in total in-flight between
round 1 and round 2), where Java's `IteratorSpliterator` grows by a fixed
increment per split instead of jumping to a cap - spreading the cost of
guessing wrong, so a pipeline that turns out to short-circuit at element 200
does not first pay a full `BATCH_SIZE`-per-worker pull to find that out. If
7.2's curve shows the knee well below `BATCH_SIZE`, a growth step may beat
both constants as they stand. Worth having that measurement vary the growth
rule, not only the cap.

**2. `gather` supplies intra-batch order; contiguity supplies inter-batch order.**

`asyncio.gather` returns results in *argument* order regardless of completion
order. Racing elements within a batch therefore costs no reordering at all, and
this is what preserves the I/O concurrency that racing exists for today —
measured at **51.8x on a GIL build** and 59.5x free-threaded on an I/O-bound
probe, which is why retiring racing is not a trade.

Across batches, order is preserved because batches are contiguous and consumed
in order. Neither property needs a buffer, an index tag or a release queue.
That is the whole argument for deleting `_guarded`'s windowed branch,
`_group_through`, `_releasable`, `_release_in_order` and `_run_ordered_tail`.

**3. `split_point()` survives; what acted on it does not.**

A stateful op still cannot run independently per batch — `sorted()` needs every
element, `distinct()` needs a global view, `limit`/`skip` need position. So the
chain still splits at the same index, decided by the same function.

What changes is the cost of the barrier. Today it means tagging elements with
source indices under a lock, buffering groups and releasing them in order.
Under fork/join it means running that one op over the batches in the order they
already arrive. The decision logic is unchanged and well-tested; the machinery
it drove is deleted.

*The alternative was considered and declined*: exploiting sized contiguous
batches to compute `limit`/`skip` from batch offsets without a barrier. It buys
parallelism on slice pipelines at the cost of new offset-accounting logic, in a
change whose purpose is removing logic. It is a good follow-up and a bad
addition here.

**4. `PROCESSES` becomes `WORKERS`.**

The name was kept deliberately, against the possibility that real parallelism
would arrive as a process pool. It has arrived as threads, so the name is now
simply wrong. Renaming is a loud `ImportError` for anyone importing it from
`snakestream.execution`, and it gets a Migration entry. Flagged as a judgment
call adjacent to the change's core rather than demanded by it — but leaving a
constant called `PROCESSES` counting threads is the kind of drift this
repository does not otherwise tolerate.

**5. `racing-encounter-order` keeps its directory name, under protest.**

Its eight requirements are stated in terms of the racing merge. The guarantees
they encode survive exactly — ordered parallel pipelines deliver in encounter
order, `unordered()` opts out, the read-ahead bound stays off the public
surface — but the mechanism named throughout is gone.

The capability path is not renamed because the workflow forbids it ("Do not
move or rename the capability"), and inventing a parallel capability while
emptying this one would leave two half-specs. The directory therefore keeps a
name describing a mechanism it no longer documents. **This is a known wart**,
recorded here rather than left for a reader to find, and the honest fix is a
separate rename once the requirements have settled.

**6. Most specs mentioning RACING need no delta, and that is the point.**

Eighteen specs mention the racing executor in passing — typically "on an ordered
`RACING` pipeline this collector takes the delivery barrier". Every such
statement remains true: an ordered parallel pipeline still delivers in encounter
order, and a collector declaring `UNORDERED` still skips the reordering. They
describe *behaviour under parallel execution*, which this change preserves
exactly, so no requirement moves.

This is the same result the PEP 695 step found: specs written as observable
behaviour survive a mechanism change, and the ones that need rewriting are
exactly the ones that named a mechanism. Their surviving textual references to
the executor's old name are corrected as prose in the same commit.

**7. This change is large, and the split is worth considering before starting.**

Stated plainly rather than discovered during implementation. It adds a public
API, replaces the execution engine, deletes ~400 lines, and reworks three
specs — one of them substantially. A reviewer cannot hold all of that at once.

The reason it is proposed whole is that the pieces resist separation: two
parallel executors alive at the same time means specifying which one
`.parallel()` binds to during the interval, and that is a temporary semantic
nobody wants to write down or test.

**There is one clean seam, and it is worth taking if the size is a concern.**
`Spliterator` is purely additive — a new module, a new public method, a new
capability, no behaviour changed and nothing removed. It can land first and be
reviewed on its own, with the executor built on it afterwards. That ordering
also front-loads the risk usefully: if the decomposition contract is wrong, it
is discovered while nothing depends on it. See **Open Questions**.

**8. `LimitOp`/`SkipOp`/`DistinctOp`'s shared state needs a real lock, found
during implementation rather than named above.**

`split_point()` only pulls an `order_sensitive` op out as a single-pass
barrier when the pipeline is *ordered* at that op's position. On
`.unordered().limit(5)`, `unordered()` clears that, and `limit`'s sink keeps
running inside the parallel portion — correctly, by design: `sink.py`'s own
docstring says `make_shared_state()` exists so "several chains … share"
state, naming RACING as the reason. Under RACING that was safe for free: every
racing branch was one more coroutine on one thread's one event loop, so
`_LimitSink.accept()`'s check-then-increment needed no lock, only the absence
of an `await` between the two halves — asyncio's cooperative scheduling did
the rest.

Fork/join breaks that for free lunch. Each batch sharing this state runs its
own chain in its own OS thread (`asyncio.to_thread`, its own event loop), so
the same compound operation is a genuine data race the moment two batches
touch it concurrently - worse on a free-threaded build, but not something a
GIL build should be trusted to serialize by accident either. This was not
named in the Risks list below when this document was written; the two
`asyncio.Lock` sites `add-free-threaded-ci-leg` flagged were, but that audit
never examined `make_shared_state()`'s `Box`/`set`, because nothing shared
across real threads existed yet for it to examine.

The fix: `LimitOp`/`SkipOp` now share a `_GuardedCounter` (a counter plus a
`threading.Lock`) instead of `Box`, and `DistinctOp` shares a `_GuardedSet`
(a set plus a lock, exposing `add_if_absent()` as one atomic operation) instead
of a bare `set`. Both live in `ops.py`, not `sink.py`'s `Box` - `Box` is also
built per composition by several collectors that never share it across
threads, and a lock there would be dead weight on every one of those paths.
The critical sections stay exactly the shape they were - check, mutate, check
again - just now inside `with state.lock:` instead of relying on there being
no `await` in between. Nothing about `limit()`/`skip()`/`distinct()`'s
observable behaviour changes; `tests/test_op_protocol.py`'s container-shape
assertion was updated to match the new types, not the guarantee it checks.

**9. `unordered()`'s delivery-order relaxation survives, conditioned on
source size — found in two passes against the running suite, the first pass
wrong in a way the second corrected.**

First pass: the initial `_fork_join_batches()` always dispatched a whole
round via `asyncio.gather()`, full stop — so `unordered()` stopped changing
delivery order for *any* pipeline, and 20 tests failed
(`test_unordered_removes_the_delivery_barrier`,
`test_an_unordered_pipeline_pays_no_head_of_line_delay`, and others in
`test_racing_delivery_order.py`/`test_racing_encounter_order.py`/
`test_unordered.py`). That looked, at the time, like a real narrowing worth
recording and shipping: decision 5 above had claimed "the guarantees survive
verbatim," which this contradicted.

It was premature. Decision 10 below fixes a *different* bug — order-blind
terminals (`any_match`/`find_any`/`count`/`for_each`) waiting on a whole
round even though their demand is `NONE` unconditionally — by making
`_fork_join_batches()` dispatch a round via `asyncio.gather()` only when
`split_point()` finds something downstream that needs order, and via a
`FIRST_COMPLETED`-based sliding window otherwise. `split_point()`'s third
clause already returns `None` for `.unordered().map(f).collect(to_list())`
just as much as for `count()` — `unordered()` clears the terminal-clause
condition regardless of what the terminal declares — so that pipeline gets
the `FIRST_COMPLETED` path too, as a direct consequence of fixing decision
10's bug rather than of anything aimed at this question. Verified
empirically: a 20-element source under `.parallel().unordered().map(slow_head)
.collect(to_list())` now delivers scrambled (`[16, 17, 18, 19, 0, 1, ...]`),
matching RACING. 17 of the 20 originally-failing tests now pass unmodified.

**What is actually true, stated once rather than revised twice more:**
`unordered()` still relaxes delivery order for a pipeline whose source spans
more than one batch in a round (more than `_FIRST_BATCH_SIZE` = 16 elements
while probing). Within one batch, `_run_batch_async()` still races its
elements via a single `asyncio.gather()` and returns them as one unit — task
2.2's own intra-batch ordering requirement, load-bearing for `flat_map`'s
cardinality change and unrelated to `unordered()` — so a source small enough
to fit in one batch delivers in encounter order regardless of `unordered()`,
which RACING's per-element branching never depended on source size for. This
is genuinely new, and it is why 3 of the 20 tests still fail: they use an
8-element source (`test_unordered.py`'s and `test_for_each_ordered.py`'s
`values = [4, 1, 7, 2, 8, 3, 6, 5]`), which now fits in one batch and so
shows no scrambling. These are the tests to widen the source on when
rewriting (task 4.3), not to delete — the guarantee they assert still holds,
their fixture no longer demonstrates it.

**Consequence for the racing-encounter-order spec.** An earlier version of
this decision had this capability's delta *remove* the delivery-order
guarantee outright. That delta is wrong and has been reverted — the
guarantee survives, so the spec keeps asserting it, restated only where the
batch-size condition needs stating explicitly (the `specs/
racing-encounter-order/` delta in this change, much smaller than the first
attempt). What *does* still need a delta is the one thing decision 10 leaves
genuinely bounded and new — an order-blind, short-circuiting terminal can be
delayed by a slow element sharing its own batch — which is a variant of the
read-ahead-bound requirement's existing, already-accepted over-pull clause,
not a new kind of claim.

**This was never a Java-parity question either way.** `BaseStream.unordered()`
is documented as "may return itself... " — permission to disregard encounter
order, never a promise to scramble it. Both the wrong first pass (never
scrambles) and the corrected second pass (scrambles when the source is large
enough) are conformant; Java makes no promise this project could have broken
here.

**10. Order-blind terminals need their own dispatch, not just their own
demand — found running `test_racing_delivery_order.py` against the new
executor, a genuine regression this change must not ship, and the fix that
corrected decision 9 above as a side effect.**

`any_match()`, `find_any()`, `count()` and `for_each()` declare
`OrderDemand.NONE` — they never asked for encounter order, `unordered()` or
not. But `_fork_join_batches()` as first written always dispatched a whole
*round* (`workers` batches) via `asyncio.gather()` and only yielded once
every batch in it returned, regardless of what the terminal declared. An
order-blind, short-circuiting terminal over an unbounded source with one slow
early element therefore waited on that element anyway —
`test_an_order_blind_terminal_holds_nothing_back` (`any_match()` finding an
element at index 3 while index 0 sleeps 5s, over an endless source) took the
full 5 seconds instead of answering near-instantly, timing out against its
2-second bound. This is not the `unordered()` narrowing (decision 9) — it
would have applied even to a chain no caller ever declared `unordered()` on,
since these terminals' demand is `NONE` unconditionally, and it works against
the proposal's own Non-Goal: "same short-circuiting."

Fixed at the round level: `_fork_join_through()` already computes
`split_point()`, which is `None` exactly when nothing downstream needs order
— no op, no terminal. That is precisely the condition under which round-level
ordering can be dropped safely. `_fork_join_batches()` now takes an `ordered`
flag and dispatches to one of two forms: `_fork_join_ordered_batches()` (the
original, round-at-a-time `gather()`) when something downstream needs order,
and `_fork_join_unordered_batches()` when nothing does — a sliding window of
up to `workers` in-flight batches, refilled and yielded via
`asyncio.wait(..., FIRST_COMPLETED)` as each one completes, rather than held
for a round. No index tag, window struct or release buffer: nothing here
restores an order that was never asked for, it only stops waiting for
irrelevant work once relevant work is ready.

**This fix is round-level, not element-level, and that boundary is
deliberate and accepted, not accidental.** Within one batch,
`_run_batch_async()` still races its elements via a single `asyncio.gather()`
and returns them as one unit — so a slow element sharing a batch with the one
a short-circuiting terminal is looking for still delays it, bounded by that
batch's size (`_FIRST_BATCH_SIZE` while probing, `BATCH_SIZE` — up to 1024 —
in steady state). Confirmed empirically: moving the matched element from
index 3 (inside the first 16-element batch, alongside the slow index-0
element) to index 17 (the next batch) takes the answer from 5.0s to 0.004s
under this fix, with no other change. Going further — streaming a batch's
results out of its worker thread element-by-element instead of returning it
as one list once `asyncio.to_thread()` completes — would close this
remaining gap, but costs a real redesign of the worker-thread boundary
(`asyncio.to_thread()` returns one value; incremental delivery needs a
cross-thread queue or callback) in a change already large. Declined for now,
consciously: the round-level fix already restores "no head-of-line delay"
for the common shape (a slow element and the terminal's target landing in
different batches, which is where most of a real source's elements are, by
construction), and the residual is bounded by one batch's worth of work, the
same order of magnitude as the read-ahead bound and over-pull trades already
accepted elsewhere in this design — not an unbounded wait. Worth reopening if
a future measurement shows the residual matters in practice.

**11. `map`/`filter`/`peek` were reclassifying their callable once per
element under fork/join — found by cross-session review after archive-readiness
was reported, independently reproduced, and fixed before archiving.**

`callable-dispatch`'s "Awaitability is classified once per composition"
requirement — Java has no equivalent, since it has no dynamically-classified
sync/async dispatch to begin with — was violated outright, not merely
narrowed. `execution._run_element()` builds a fresh sink chain per element
(deliberately — see its own docstring on why a per-element bridge is needed
for `gather()`-based intra-batch concurrency), and `_FilterSink`/`_MapSink`/
`_PeekSink` each classified their callable in their own `__init__` via
`AsyncDispatch._init_dispatch()`. A sink built once per composition (every
other executor's shape, and what the class's own docstring assumed) makes
that one classification per composition; a sink built once per *element*
makes it one classification per element instead. Measured: 500 elements
through `.map(f).filter(p)` called `is_async_callable()` 3 times sequentially
and 1001 times under `.parallel()` — reproduced independently before fixing,
matching the reviewer's own count exactly.

This is the exact pattern roadmap.md's Done log already declines four times
("The per-element dispatch dance, re-examined and declined a fourth time",
2026-09-03) — not the same code path, but the same shape: per-element
reclassification the project has repeatedly rejected as both slow and a
guarantee this capability specifically exists to make. It was reintroduced
silently by this change, not proposed and accepted.

**Fix:** awaitability is a pure function of the callable, and the callable is
fixed for an `Op`'s lifetime — `Op` instances are already reused across every
composition (`pipeline-composition`) — so classify once there instead of once
per sink. `ops.py`'s new `_SinglePureCallableOp` (the shared base
`FilterOp`/`MapOp`/`PeekOp` now extend) classifies at construction and passes
the result into its sink, which `AsyncDispatch._init_dispatch()` now accepts
as an optional precomputed `is_async` rather than always recomputing it. This
satisfies "at most once per composition" with room to spare — once ever, not
once per composition — and needed no change to `_run_element()`'s per-element
bridge, whose reasoning stands independent of this bug.

**Why section 3's audit gate didn't catch it, and what that means for change
3.** The gate's question was "does this test map to a surviving spec
requirement?", applied only to tests already living in the racing-executor
files. It never asked the inverse — "which *other* specs might the new
implementation violate?" — so `callable-dispatch` was never in the blast
radius `test-audit.md` considered, since nothing in that capability mentions
racing or fork/join by name. `benchmark-findings.md`'s own honesty is what
surfaced it: the reviewer traced the "two orders of magnitude larger than
estimated" cheap-mapper regression that benchmark flagged straight to this
bug. Worth carrying into the combiner change (roadmap.md, **Now**): an
inverse sweep — which existing capability's requirements does the new
mechanism's *shape* put at risk, not just which tests already reference it —
belongs in that change's own audit gate from the start.

A `callable-dispatch` spec delta was added (narrower than it sounds): the
"Awaitability is classified once per composition" requirement now states the
per-`Op` mechanism as what satisfies it under fork/join, and the "Each
parallel branch classifies independently" scenario is corrected — it no
longer describes each batch computing its own answer and happening to agree,
since it now reads the one answer already computed on the shared `Op`. No
observable behaviour changed for a caller; every dispatch requirement in that
capability's "Uniform sync/async callable dispatch" and "Classification state
is per callable" sections holds exactly as before, since re-classifying an
identical callable per element cannot itself have produced a wrong classify
answer with a real interpreter — the amount of *work* was what changed, and
was over-run rather than the correctness. A regression test
(`test_classification_is_not_repeated_per_element_under_fork_join`) pins the
call count; deliberately reverting the fix and re-running it confirmed it
fails (1003 calls) before confirming it passes with the fix restored (5
calls).

## Risks / Trade-offs

- **Cheap callables regress.** Chunking costs where per-element work is below
  ~1.4µs. **Corrected by task 7.2's benchmark (benchmark-findings.md):** this
  does NOT stay bounded at O(workers) — the design-time +1.5ms/0.3ms-pipeline
  estimate significantly understated it. It scales with the number of
  `asyncio.to_thread` batch dispatches, which grows with source size once past
  round 1 (roughly source-size / `BATCH_SIZE` dispatches at steady state): the
  measured regression at `n=8192` on a cheap sync mapper was ~83-88ms against a
  ~4ms sequential baseline (not +1.5ms), of which ~18ms was a separate, real
  bug — per-element reclassification of `map`/`filter`/`peek`'s callable,
  caught by cross-session review and fixed the same day (see
  benchmark-findings.md's correction and the `callable-dispatch` delta) — not
  part of the batch-dispatch cost this bullet is about. The corrected,
  post-fix regression is ~72ms, still driven by batch-dispatch count as
  below. It is explicitly accepted regardless —
  it is a real regression for `.parallel().map(lambda x: x + 1)` either way,
  and `.sequential()` is the answer for it — but a reader sizing the cost
  should use the corrected figure, and the fix is not "bound it at O(workers)"
  since it already isn't. The same benchmark confirmed the one-step batch-growth
  jump (4 → `BATCH_SIZE`) is the right call *because* of this cost, not despite
  it: a smoother, Java-style incremental growth rule multiplies dispatch count
  ~10x for the same source and made the regression worse, not better — see
  task 7.2's note below and benchmark-findings.md's "Batch-growth curve"
  section, which resolves this decision's "for 7.2, not decided here" addendum
  in favour of keeping the one-step jump.

- **`asyncio.Lock` in a threaded world.** The obligation
  `add-free-threaded-ci-leg` recorded: `execution.py`'s two lock sites are not
  thread-safe across event loops. Under fork/join the shared-source pull happens
  only on the main loop, so the *hazard* mostly dissolves rather than being
  fixed — but that must be verified rather than assumed, and any surviving
  cross-thread state needs `threading.Lock`.

- **Exceptions cross a thread boundary.** A user callable raising inside a
  worker must surface with its traceback intact and must not leave other workers
  running. `asyncio.to_thread` propagates through the await, but cancellation of
  sibling batches on first failure needs explicit handling — today's
  `_racing_branches` teardown did this and is being deleted.

- **Short-circuiting over-pulls by up to one batch per worker.** `limit(3)` on a
  1024-element batch materialises 1024 elements. Today's window bounds this more
  tightly. Mitigated by making the *first* batch small, and measured against
  `pipeline-composition`'s existing "limit() short-circuits without over-pulling
  upstream" requirement, which this change must not violate.

- **Deleting 400 lines removes tested behaviour. This is the change's principal
  risk.** 125 tests across four files sit in the blast radius —
  `test_racing_encounter_order.py` (44), `test_racing_delivery_order.py` (41),
  `test_execution_model.py` (27), `test_parallel.py` (13) — plus scattered
  references in five more files and `conftest.py`. Some assert a *mechanism*
  that is genuinely gone; others assert a *guarantee* that still holds. They are
  hard to tell apart because both live in files named after the racing executor.

  → Mitigated by making the audit a **gate** rather than a step: `tasks.md`
  section 3 builds a full inventory and classifies every entry against a
  surviving spec requirement *before* section 4 deletes anything, and records
  the classification in the change directory as a reviewable artifact.

  **The failure mode is silent, which is why it needs the gate.** A guarantee
  losing its only assertion leaves a passing suite and a green coverage gate —
  the deleted code and its test leave together, so the percentage does not move.
  Coverage is therefore explicitly *not* accepted as evidence here; task 4.7
  re-checks the table against the tree instead, and task 4.3 requires each
  rewritten test to be deliberately broken once to prove it still catches what
  it claims to.

## Open Questions

**Should `Spliterator` land as its own change first?** This is a question about
review risk, not about design — the plan is the same either way, only its
packaging differs. It is listed here rather than decided because the answer
depends on how the work will be reviewed, which is not the author's call. If the
answer is yes, this change splits at decision 7's seam with no rework: the
`stream-spliterator` capability and its module move to a change of their own,
and everything else stays here.

Nothing else in this document depends on the answer.
