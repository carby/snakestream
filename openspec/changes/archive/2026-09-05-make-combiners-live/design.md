## Context

See `proposal.md` — Why, and the two archived predecessors for the sequence.

The state that shapes this change:

- `Collector` has carried a `combiner` slot since 2026-08-17 and has never
  invoked it. **All fifteen** built-in collectors construct
  `Collector(supplier, accumulator, ...)` with the slot empty — verified, not
  assumed.
- `_ForkJoin` inherits `Executor.value()`'s generic
  `_drain(self.elements(...), terminal)`. Batches run the *chain* in worker
  threads; the terminal's `accept()` runs on the main loop, once per element,
  into one container.
- `_Sequential.value()` already overrides the generic form with
  `_feed_through()`, purely on measurement. So the protocol already tolerates an
  executor supplying its own `value()`; this change adds the second such
  override rather than introducing the idea.
- `reduce()` has two overloads and dispatches on `UNSET`; the two-argument form
  already widens (`Accumulator` is `(T | R, T) -> T | R`).

## Goals / Non-Goals

**Goals:**

- Make both combiners live, in one change, so neither ships as a promise the
  other has to keep.
- Close the measured 0.98x gap for work living inside a collector.
- Keep every existing call site's result **identical**. This change is about
  where work runs, not what it produces.

**Non-Goals:**

- `Characteristics.CONCURRENT` and `IDENTITY_FINISH`. Java has them; neither is
  needed to merge partitions, and adding enum members nothing reads would be
  parity theatre.
- Tuning partition granularity. A partition is a batch, because a batch is what
  the executor already has; whether a different granularity is better is task
  7's measurement, not a design assumption.
- Making the float family combinable by summing pairwise or with Kahan
  compensation. That changes results — for the better, arguably — and a change
  whose stated goal is identical results is the wrong place for it.

## Decisions

**1. The partition protocol lives on `TerminalSink`, and it needs a factory.**

The executor is handed a terminal sink *instance* (`self._evaluate(ReduceSink(...), ...)`),
so partitioning cannot mean "call it more times" — it needs more sinks. The
protocol is therefore a way to spawn a peer and a way to merge one back:
roughly `can_partition()`, `new_partition()`, `merge_from(peer)`, with the base
declining by default so every terminal that does not opt in behaves exactly as
today.

*Alternative considered — have `_ForkJoin.value()` inspect the terminal's type
and reach for its collector.* Rejected: it puts knowledge of `CollectorSink`
and `ReduceSink` into `execution.py`, which currently knows about neither, and
it would need extending for every future partitionable terminal.

**2. A partition is a batch, and merging is left fold in batch order.**

The executor already produces contiguous batches in encounter order. Reusing
that as the partition boundary means no new decomposition, and it is what makes
associativity sufficient: partitions are contiguous runs merged left to right,
which is Java's own requirement and not a stronger one.

`unordered()` deliberately does **not** relax this. It releases the requirement
to *deliver* in encounter order; merging partials in arbitrary order would
require commutativity, which no caller has asserted by supplying a combiner. The
spec states this explicitly because the inference "unordered, so merge order
cannot matter" is exactly the plausible-looking mistake to guard against.

**3. Leaf combiners where associativity holds; derived combiners from
downstream.**

The derivation is not an invention — `mapping()` and `collecting_and_then()`
already derive `characteristics` from their downstream, and Java builds
`groupingBy`'s combiner from its downstream's. Reusing the shape means a reader
learns one rule, and a composite over a non-combinable downstream degrades to
today's behaviour rather than to a wrong answer.

**4. The float family is excluded, and the reason is stronger than the one that
already excludes it from `UNORDERED`.**

`summing_double`, `summarizing_double` and **all three** `averaging_*` accumulate
into a `float` — `_AvgBox.total` is `float` and one `_averaging()` serves all
three, so `averaging_int` is excluded too despite its integral element type.
Float addition is not associative, so partitioning changes the result.

The distinction worth keeping straight, and stated in the spec because it is
easy to conflate: `UNORDERED` is about whether *delivery* order may be
disregarded; a combiner is about whether *partial results* may be merged. They
are independent. `min_by`/`max_by` are the proof — they decline `UNORDERED`,
because which of two tied elements wins must follow encounter order, yet they
combine perfectly well, because a left-biased merge over contiguous partitions
preserves exactly that tie-break.

**5. `to_map` splits on arity, and this is a real behavioural line.**

The two-argument form's collision rule is "raise"; merging two partial maps
raises on a key present in both, which is the same rule the accumulator
applies. It partitions. The three-argument form takes a caller's
`merge_function`, which is nowhere required to be associative — lifting it into
a combiner would silently impose a contract the caller never agreed to. It does
not partition.

**6. Identity is a contract, and the library will not check it.**

Each partition starts from `identity`, so a value that is not an identity for
the combiner contributes once per partition. `reduce(0, add, add)` is correct;
`reduce(10, add, add)` is not, and returns a different answer under `.parallel()`
than under `.sequential()`.

Java states the same requirement and does not verify it. Verifying is not
possible in general — it would mean calling the combiner with a probe value and
comparing, which assumes equality is defined and cheap and that the combiner is
pure. So the spec states it as a caller contract and the README migration entry
names the failure mode, which is the only honest option.

## Risks / Trade-offs

- **A partitioned reduction silently disagrees with the sequential one.** The
  central risk, and the reason the acceptance test is *equality with sequential*
  rather than "the combiner was called". Every collector gaining a combiner
  needs a test asserting the parallel result equals the sequential result over a
  source spanning several batches — not a source small enough to be one
  partition, which would pass without ever merging.

- **Merging costs more than the accumulation it parallelised.** Real for cheap
  accumulators: `to_list`'s merge is `list.extend` per partition against
  `list.append` per element, which is favourable, but `counting`'s merge is an
  addition against an addition. The measured gap this change exists to close is
  in collectors carrying a *user callable*; the trivial ones may gain nothing.
  Task 7 measures per collector, and a collector where the combiner measurably
  loses should have it removed rather than kept for symmetry.

- **The audit gate's blind spot from the last change applies here.** Section 3
  of `fork-join-executor-and-spliterator` asked "does this test map to a
  surviving requirement?" and never asked the inverse — *which specs might the
  new implementation violate?* — which is how the `callable-dispatch`
  regression reached review. This change adds a partitioned execution path that
  the whole collector suite is untested against, so the inverse sweep is a task
  here, not an afterthought.

- **`_run_element()`'s per-element sink construction interacts with this.** A
  partitioned terminal is built per *batch*, not per element, so the terminal
  side is not affected — but the chain side still builds a sink chain per
  element, and anyone measuring this change's numbers should know that cost is
  present in both arms rather than attribute it here.

## Open Questions

**Does the partition boundary want to be the batch?** It is what the executor
has, and decision 2 takes it. If task 7's per-collector measurements show the
merge dominating for cheap accumulators, a coarser partition — one per *worker*
rather than per batch, accumulating across that worker's batches — would cut the
merge count without changing any contract. Deferred deliberately: it is a tuning
question, answerable with numbers this change will produce, and it changes no
spec.
