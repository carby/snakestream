## Context

See `proposal.md` — Why. The design-relevant facts about the current code:

- `_CollectorSink` (`collector.py:126`) already **is** a `TerminalSink`. It
  classifies `collector.accumulator` through `AsyncDispatch`, calls
  `supplier()` from `_create_container()` and `finisher()` from `_finish()`,
  and is built fresh per `collect()` call, so no classification state leaks
  between compositions or across `RACING`'s branches.
- `_MutableReductionSink` (`terminals.py:122`) is the same two bases, the same
  `AsyncDispatch` triple and the same `accept()` body. It differs only in
  where the container comes from: `Stream._collect_mutable()` awaits the
  supplier itself and hands the result to the constructor, so
  `_create_container()` returns a stored attribute.
- `TerminalSink.begin()` routes `_create_container()` through `_maybe_await`,
  and `TerminalSink.end()` routes `_finish()` the same way. Both are stated in
  that class's docstring as a contract three call sites already depend on. The
  supplier therefore needs no separate awaiting once it lives on a `Collector`.
- `Collector.__init__` takes `(supplier, accumulator, combiner=None,
  finisher=None, characteristics=_NO_CHARACTERISTICS)` — the three-argument
  `collect()` form's parameters, positionally, in order.
- `Stream.collect()` already runs `_check_not_consumed()` itself, and
  `_evaluate()` runs it again; the check is a read, so calling it twice is
  harmless — `to_array()` already relies on that.
- `stream.py` already imports `Collector` and `_CollectorSink` from
  `collector.py`, so no import edge or cycle is introduced.

## Goals / Non-Goals

**Goals:**

- One collection sink in the library. After this change every remaining sink in
  `terminals.py` exists for a stated reason that is not duplication:
  `_CountSink`, `_ReduceSink` and `_MinMaxSink` on the measured
  `collapse-terminal-collector-duplication` gate; `_ForEachSink` because it has
  no container; `_FindSink` and `_MatchSink` because `Collector` cannot express
  `cancellation_requested()`.
- Keep every existing test passing **unedited**. A test edit here is evidence
  of a behaviour change, not of a test that needed updating.
- Produce a defensible number for the per-element cost, recorded whichever way
  it lands, so this is never re-argued on shape alone — the posture
  `add-callsite-dispatch` established.

**Non-Goals:**

- Touching `_ForEachSink`, `_FindSink` or `_MatchSink`. The Non-Goal reason
  `collapse-terminal-collector-duplication` gave — no collector counterpart —
  is correct for all three and remains so.
- Re-opening `_CountSink`, `_ReduceSink` or `_MinMaxSink`. Those are a
  measured, deliberately-rejected trade, not an open cleanup.
- Making `_CollectorSink` faster in general, or changing `Collector`.
- Declaring any `Characteristics` on the three-argument form (Decision 3).

## Decisions

### Decision 1: Build a `Collector` at the call site, rather than keeping a sink that wraps one

`collect()`'s three-argument branch constructs
`Collector(supplier, accumulator, combiner)` and hands it to the same
`_CollectorSink` the single-argument branch uses. The alternative — keep
`_MutableReductionSink` and have it hold a `Collector` internally — preserves a
class whose entire content would then be delegation, and leaves two sinks for
one job, which is the thing being removed.

Direction matters here as it did in `collapse-terminal-collector-duplication`
Decision 1, and lands the same way for the same reason: the `Collector` is the
more general object. It must work when a caller supplies it to `collect()`, and
it must be reusable across concurrent collections. Folding the general onto the
special would mean the collector path keeps everything it has *and* gains a
dependency on a sink.

The combiner rides along in `Collector`'s own combiner seat, still never
invoked. That is the change's quiet second product: the "accepted for parity,
never called" posture is stated once in code instead of twice, and
`collector-protocol`'s and `mutable-reduction-collect`'s two separate
requirements about it now describe one mechanism.

### Decision 2: The `collapse-terminal-collector-duplication` gate applies, and this passes it

That change's threshold — **+10% ns/element on the sync variant**, Python
3.14.5, 20,000 elements, best-of runs — is this change's gate too, unmodified.
It is the level this repo has treated as real, and re-deriving it would only
weaken the comparison.

What failed the gate there does not exist here. `counting()`, `reducing()` and
`min_by()` keep their per-collection dispatch state on a supplier-made box and
wrap the user's callable in their own `async def _accumulate`, so routing a
terminal through them added a Python-level coroutine frame plus an attribute
hop per element. The three-argument `collect()` form has no box and no wrapper:
its `accumulator` is a `BiConsumer(container, element)`, which is exactly a
`Collector`'s accumulator, invoked directly by `_CollectorSink.accept()` — the
same source text `_MutableReductionSink.accept()` runs today, on the same class
shape, through the same `AsyncDispatch` attributes. The two paths differ only
in `_create_container()` and `_finish()`, both once per composition.

Measured, ahead of implementation, on 20,000 elements, interleaved round-robin
between the two variants (the block-sequential drift trap
`extract-racing-task-lifecycle` recorded), best of 3 across 10 rounds, three
independent runs, ns/element:

| variant | `_MutableReductionSink` | via `_CollectorSink` | delta |
|---|---|---|---|
| sync accumulator | 322.5 / 333.7 / 344.6 | 310.3 / 317.9 / 331.6 | −3.8% / −4.7% / −3.8% |
| async accumulator | 420.1 / 425.5 / 401.1 | 388.7 / 441.4 / 408.7 | −7.5% / +3.7% / +1.9% |

No systematic direction and spread inside the ~10% run-to-run noise this
harness has shown before — which is what an identical per-element path looks
like, and is the evidence for the claim rather than a claim of a speed-up. The
gate is re-run against the shipped code, not against this prototype.

### Decision 3: The three-argument form declares no `Characteristics`, and so keeps `OrderDemand.IF_ORDERED` by derivation

`_collect_mutable()` passes `OrderDemand.IF_ORDERED` explicitly today, with a
comment stating why: an arbitrary user accumulator folding into an arbitrary
container says nothing about being order-independent, and the `Collector` form
has `UNORDERED` to say otherwise while this form has no way to.

Constructing a `Collector` with the default empty `characteristics` preserves
that answer *through the existing derivation* rather than beside it —
`collect()`'s Collector branch reads `Characteristics.UNORDERED in
collector.characteristics`, which is `False` for an empty frozenset, giving
`IF_ORDERED`. One site reads characteristics instead of two sites picking a
demand.

Rejected: passing `OrderDemand.IF_ORDERED` explicitly from the three-argument
branch anyway, as insurance. It would leave two statements of one fact that can
drift, which is the defect this whole change is about. The comment explaining
*why* the form cannot declare `UNORDERED` must survive the deletion, moved to
the construction site.

### Decision 4: The supplier's `_maybe_await` moves onto the contract that already owns it

Deleting `_collect_mutable()` deletes `await _maybe_await(supplier)`. The
supplier is then awaited by `TerminalSink.begin()`, which routes
`_create_container()` through `_maybe_await` — a contract that class's
docstring already documents and that `_CollectorSink._create_container()` (which
returns a possibly-async supplier's result un-awaited) is already the primary
example of.

Two observable properties are preserved rather than assumed, and are asserted
in tasks:

- **Called exactly once, before the first pull.** `begin()` runs once per
  composition under both executors: `Sequential.value()` → `feed_through()` →
  `_copy_into()` calls `head.begin()`, which propagates down to the terminal,
  before its `async for`; `Racing.value()` → `drain()` → `_copy_into(terminal,
  ...)` begins the terminal before the first element is pulled from the
  lazily-constructed `elements()` generator.
- **A raising supplier still raises before any element is seen**, out of the
  same awaited coroutine. Only the traceback's interior frames change.

### Decision 5: The `combiner` type mismatch gets a `cast` and a comment, not a signature change

`collect()`'s overload types the combiner `BiConsumer[R, R]`
(`Callable[[R, R], Awaitable[None] | None]`); `Collector.__init__` types it
`Combiner[A] | None` (`Callable[[A, A], A | Awaitable[A]]`). The return types do
not unify, so `ty` is expected to reject the construction.

The parameter is inert under both types — never invoked, by two separate
requirements — so the honest fix is a `cast` at the single construction site
with a comment naming the mismatch. Java carries the identical one:
`Collector.of` takes `BinaryOperator<R>` where
`collect(Supplier, BiConsumer, BiConsumer)` takes `BiConsumer<R,R>`, and the
javadoc asserts the equivalence across it.

Rejected: widening `Combiner` or narrowing the overload. Both change a declared
public type surface to serve an internal refactor, and one of them would let a
`Collector` accept a combiner shape its own requirement does not describe.

## Risks / Trade-offs

- **[The gate fails on the shipped code, unlike on the prototype]** → Revert to
  `_MutableReductionSink` and record the figures in the roadmap **Done** entry
  as a measured rejection, exactly as `collapse-terminal-collector-duplication`
  did. The change is not committed before the gate is re-run.
- **[Supplier timing shifts from "before `_evaluate`" to "inside `begin()`"]** →
  Both are before the first pull under both executors (Decision 4). Covered by
  an explicit task asserting call-count and ordering, and by
  `mutable-reduction-collect`'s existing "Empty stream still returns a
  container" scenario.
- **[Coverage falls below the 98% gate]** → Deleting a well-covered sink
  changes the denominator. Check whether a `_CollectorSink` branch became
  reachable from a second direction before adding any test; a coverage dip that
  needs a *new* test is a signal the collapse was not behaviour-preserving.
- **[`ty` rejects the construction]** → Expected, and Decision 5 is the answer.
  A `cast` added reactively at the site `ty` names, never preemptively.
- **[Someone later reads this as licence to re-collapse the other sinks]** →
  The proposal and this document both state the distinction — counterpart
  versus no counterpart, box versus no box. The roadmap **Done** entry repeats
  it.

## Migration Plan

None. No public API, signature, return type or observable behaviour changes, so
there is no migration-log entry — and that absence is a claim, not an
oversight. Rollback is reverting the commit; the deleted sink has no persisted
state and no external caller.
