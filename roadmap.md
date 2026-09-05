# Roadmap

Now/Next/Later view of open code-quality and test-rigor items. **Done** is the
history, and is specifically the *rejection* log: several entries there record
work that was measured and declined rather than shipped, which the openspec
archive does not carry because a rejected change often has no archive at all.
Read it before proposing a cleanup.

**Guiding principle (stated 2026-08-21):** keep a 1:1 match on the *public API
surface*, and exploit Python's capabilities *underneath* for simplicity and
performance. Java is the API contract, not the implementation blueprint. A
divergence from Java's internals is not a defect; a divergence in observable API
behaviour is — that framing is what found the position-dependent `.parallel()`
bug. Where Java's structure exists only to solve a Java problem, drop it: one
`_copy_into()` where Java needs `copyInto()` plus `copyIntoWithCancel()`,
`_maybe_aclosing()` as an `@asynccontextmanager`, collectors as one `Collector`
value rather than a class hierarchy, `summing_int`/`summing_long` sharing a body.

## Now

**Entry criterion: scoped, unblocked, and available to start.** Nothing here is
claimed — the bucket is a pool, not a commitment. What decides an item's bucket
is what stands between it and someone starting: nothing (**Now**), a person
(**Next**), or a decision nobody has made yet (**Later**).

### Re-verified 2026-09-05, formerly a **Later** row

**1. Bound speculation separately from read-ahead.** One counter served three
concerns — memory held by the reorder buffer, latency behind a straggler, and
how many elements a chain callable runs on under a short-circuiting terminal.
Filed in **Later**, then marked *"Moot as of `fork-join-executor-and-spliterator`
(2026-09-04)"*. **That verdict was wrong and is withdrawn.** Half the row died
with the racing executor; the other half is live, and moved here because
nothing about it is decision-blocked any more — the real-parallelism call it
was parked behind is resolved, and what remains is a benchmark against an
existing harness.

*Dead half:* the row's own worked example, `.peek(fn).find_first()`.
`find_first()` demands `ALWAYS`, so it splits at the chain end, runs ordered,
and is answered by round one — bounded at `WORKERS * _FIRST_BATCH_SIZE` = 16
chain invocations, which is what the old window gave, now by a number that
means only that.

*Live half:* the same waste under an **order-blind** short-circuiting terminal.
`execution.py:432` sets `size = BATCH_SIZE` after the first *completed batch*,
not after a full round, so `.peek(fn).any_match(p)` that is not satisfied inside
the first 16 elements escalates straight to `WORKERS * BATCH_SIZE` ≈ 4096
elements in flight, every one running the whole chain. The old racing window's
total was 16. CLAUDE.md already concedes the concern "still applies at this
size"; this row is where that concession is actionable. `unordered()`, the
documented lever, does not help — the order-blind path is the one that
escalates fastest.

*Not analysed further here, deliberately.* The verdict is alive-or-dead only;
the sizing question (should the escalation hold a smaller step longer under a
short-circuiting consumer?) is open work, not a conclusion. One thing worth
knowing before starting: `fork-join-executor-and-spliterator` task 7.2 already
settled the **growth rule** — a Java-style +4-per-round increment measured 10x
more dispatches and ~2x worse wall time than the shipped one-step 4 -> 1024
jump — but never measured the first-round value `4` itself, which
`execution.py:196` still describes as "a starting point, not a measurement".

### Surfaced 2026-09-03, by the `extract-encounter-order-model` move

Not claimed. Not scaffolded — recorded as a diagnosis, not as available work.

**1. `UNSET`, `unseeded()` and `Box` sit in `sink.py` on the same
import-topology reasoning `extract-encounter-order-model` rejected for the
encounter-order model.** `UNSET`'s own comment says why it landed there:
"Lives here rather than in `terminals.py` or `collector.py` because both need
it and neither may import the other" — placement decided by which module both
callers could already reach, not by what `sink.py`'s docstring says the module
is for (the push protocol). It is the identical shape `Ordering` and
`is_ordered()` were moved out of.

**Narrowed 2026-09-03 by `name-by-visibility-not-underscore`:** the naming
half of this is now moot — all three were underscored and cross-module, and
that change's rule made them bare (`_UNSET` -> `UNSET`, `_unseeded()` ->
`unseeded()`), the same as it did to `_split_point()`. What is left is only
the module-placement question the title names: whether these three earn a
fourth module, fold into an existing one, or stay put on the grounds that a
sentinel and a rule-with-a-name are a smaller, more defensible exception than
four symbols were. Still a call for whoever picks this up — not settled
here.

## Next

**Entry criterion: claimed.** Someone has committed to doing it next. That is
the only thing that moves an item here from **Now**.

### Claimed 2026-09-02

Two duplications surfaced by the same read that produced
`collapse-mutable-reduction-onto-collector` (scaffolded the same day, and
deliberately *not* listed here — it has its own change directory). Both were
passed over for that one because it was the only candidate whose per-element
path is provably unchanged; each of these needs a measurement the collapse did
not. **Ranked as listed, most valuable first.** Read each item's gate before
starting: both sit on a per-element path, which is where every measured
rejection in **Done** has happened. A third item from this batch is already
closed; see **Done**.

**1. `comparator.py`'s segment-sign 2x2.** `_key_segment_sign_sync`,
`_key_segment_sign_async`, `_comparator_segment_sign_sync` and
`_comparator_segment_sign_async` are one function written four times: the
natural-ordering expression `(ka > kb) - (ka < kb)` appears in all four, and so
does the null-tie clause `0 if <a> is None and <b> is None else _null_sign(...)`.
The shape underneath is that **a key segment is a comparator segment whose
comparator is natural ordering** — which is the unification, and also the
reason it cannot be done by normalising the payload: `sort.py`'s
`_segment_column()` dispatches on `isinstance(payload, tuple)` to choose between
a plain key column (compared in C) and a `cmp_to_key`-wrapped one, and that
distinction is the decorate-sort-undecorate fast path. So the payload shapes
stay and only the sign functions merge.

*The gate.* These four are reached only through `KeyComparator.__call__`, which
`sort()` never uses — it unwraps `.segments` instead. The live consumers are
`min()`/`max()` and `min_by()`/`max_by()`, at one comparison per element. That
is a per-element path, so the `collapse-terminal-collector-duplication`
threshold (+10% ns/element, sync variant) applies unchanged. `is_new_extremum`'s
own docstring already records what this neighbourhood costs: delegating its type
check measured ~5%.

**2. `collectors.py`'s per-box dispatch state.** Nine `_*Box` dataclasses carry
14 `(<name>_is_async, <name>_checked)` pairs — 28 field declarations — plus a
`_supply()` that re-seeds them from `is_async_callable`. It is `AsyncDispatch`'s
three pieces of state, written out longhand once per collector, because a
`Collector` is reusable across concurrent collections and so cannot hold
classification on itself the way a sink does.

*The gate, and it is the hard one.* Every consolidation that suggests itself —
a shared base box, a `Dispatch` slot object, routing the four hand-inlined
accumulators through the existing `_classify_step` — adds either an attribute
hop (`container.key.is_async` for `container.key_is_async`) or a tuple
allocation on the per-element path. That is precisely the charge that killed
`add-callsite-dispatch`, `collapse-terminal-collector-duplication` and the
`merge()` generator in `extract-racing-task-lifecycle`. **This is the largest
literal duplication in the repository and the one most likely to be rejected
again.** Anyone starting it should write the benchmark before the refactor, and
should expect the answer to be "extract the *declaration* (the box's fields and
their seeding) while leaving the per-element dance inlined" rather than a clean
collapse.

*Sharpened 2026-09-03* by the read recorded in **Done** below. That predicted
answer now has a reason behind it rather than only a benchmark: the
declaration is precisely the part carrying the structural guarantee, because
per-composition classification is a property of *where the state is
allocated* — here, a box the supplier builds once per collection — and not of
the lines that read it. So a shared base box is admissible only while it
stays allocated per collection. One that did not would trade the cheapest
safety property in the package for line count, and would do it silently: the
behavioural tests would still pass, since every one of them collects once.

## Later

**Entry criterion: blocked on a decision, not on effort.** Every item here
needs an explicit call before it can start — on a core semantic, on a trade-off
nobody has agreed to take, or on a divergence from Java. Being big or unscoped
is not what puts something here; being *undecided* is.

**Three items, numbered below.** 1. `async with` on `Stream`. 2. Java 9
additions. 3. `Stream.of()`'s arity-dependent semantics. They are in two
shapes — one prose entry and a two-row table — because the table's "why later"
column is what a reader compares across rows, and item 1's reasoning does not
fit a cell. The numbering is the index; the shapes are not a ranking.

**1. `async with` on `Stream`.** Parked 2026-08-31, from the
`implement-python-data-model` exploration. That change implements the
*synchronous* context manager (`__enter__`/`__exit__`) and deliberately stops
there. `CloseHandler` is a plain no-arg sync callable and `close()` invokes
handlers without awaiting, so `with` is the honest protocol for the
close-handler contract as it stands. Adding `__aenter__`/`__aexit__` would be
a claim that a handler may be awaitable — a change to the
`stream-close-handling` capability, not to the two methods. It belongs here
rather than in **Now** because it needs the same kind of buy-in the rest of
this section does: `close()` becoming awaitable, or growing an async twin,
changes a contract every subclassed resource wrapper depends on. Nothing
blocks it; nothing yet demands it either.

Bigger, structural — needs explicit buy-in before starting since it changes a
core semantic.

**Resolved 2026-09-04 by `fork-join-executor-and-spliterator` (see Done):**
three rows formerly here — real parallelism, `spliterator()`, and the
combiners those two gated — are gone from this table. `spliterator()` is
implemented. `.parallel()` runs on real OS threads now, and delivers genuine
CPU parallelism on the free-threaded build (3.14t, PEP 779); the
`ProcessPoolExecutor`/pickling blocker the old real-parallelism row described
never applied to a thread-based design, since nothing crosses a process
boundary. Full multiprocess parallelism is not implemented and nobody has
asked for it now that threads deliver the real thing on the free-threaded
build; if it resurfaces, it is a fresh decision, not a continuation of this
row, so it is not re-filed here speculatively. The combiner item is no longer
sequenced behind a decision — `spliterator()`'s contiguous decomposition,
its load-bearing prerequisite, is shipped — so it moved to **Now**, was taken
as `make-combiners-live`, and is in **Done** (2026-09-04); the **Queued
changes** block this sentence used to point at was retired on 2026-09-05 with
the rest of the Java 8 queue. That entry carries the (a)/(b)/(c) findings the
old row here recorded.

| Item | Why later |
|---|---|
| **2. Java 9 additions** — six, not four. `Stream`: `takeWhile(predicate)`, `dropWhile(predicate)`, `Stream.ofNullable(t)`, and the 3-arg `iterate(seed, hasNext, next)` overload (distinct from the already-implemented 2-arg `iterate(seed, next)`). `Collectors`: `filtering(predicate, downstream)` and `flatMapping(mapper, downstream)`, which this row omitted until 2026-09-05. | **Not gated on Java 8 any more — Java 8 is closed** (2026-09-05, see Done: zero gap rows across all three README tables). README gates Java 9 on "some sort of feature parity with Java 8" and that gate is now met outright rather than argued. What keeps this row here is the bucket's own criterion: it is **undecided**, not blocked. Nobody has called whether Java 9 becomes a tracked effort the way `Collectors` parity once was, whether only the items with independent merit get cherry-picked, or whether Java 8 is the destination and Java 9 stays opportunistic. That call is the entry ticket, and it is deliberately not made here. **Effort, for whoever makes it:** four of the six are near-free — `ofNullable` and the 3-arg `iterate` are a static and an overload widening in `stream.py`, and `filtering`/`flatMapping` are downstream-deriving collectors on `mapping()`'s exact shape (combiner and characteristics derived from the downstream). Only `takeWhile`/`dropWhile` carry design weight: both are `order_sensitive` in the sense `limit`/`skip`/`distinct` are — the answer depends on an element's *position* — so each needs an `Ordering` declaration and forces a `split_point()` in an ordered fork/join pipeline, and `takeWhile` needs `limit`'s cancellation in its sink besides. That is declaring two ops into machinery built for them, not new machinery. |
| **3. `Stream.of()`'s arity-dependent semantics** — `Stream.of([1, 2])` spreads the single collection into two elements, while `Stream.of([1, 2], [3, 4])` yields two lists. The number of arguments changes what the arguments mean, there is no way to express a stream of exactly one list, and Java's `of(T...)` treats every argument atomically. | Decision-blocked rather than effort-blocked, which is what this bucket is for. The spreading form is not an oversight: it is the primary documented idiom, used in nearly every README example and throughout the test suite, and `Stream.iterate()` is built on it. Changing it would be a far larger break than the `str`/`bytes` and kwargs changes already in the migration log, touching essentially every call site in the docs and tests. Needs an explicit call on whether Java parity is worth that, or whether the divergence should be declared permanent. **Narrowed 2026-08-31: the behaviour is now documented in README's `of()` row.** That was a defect independent of this decision — the row described Java's semantics, so the divergence used by every example in the file was invisible to a reader. Documenting it does not close this item; what remains is the call on whether to keep it. Surfaced 2026-08-20 in the same code-quality read that produced the first batch of **Now** items, all since closed. |

## Done

- **Java 8 parity is closed** (2026-09-05) — the five gaps
  `enumerate-java-8-parity-gaps` (2026-08-31) enumerated are all shipped, and
  the **Now** entry queueing them is retired. This is the answer, not a status
  update: there is no Java 8 parity gap left to point at, and the tables can be
  re-counted in a minute (below) rather than re-argued.

  | gap | closed by | when |
  |---|---|---|
  | `reduce(identity, accumulator, combiner)` | `3be5ed1`, `make-combiners-live` | 2026-09-05 |
  | `to_map(key_mapper, value_mapper, merge_function, map_supplier)` | `f6406fe` | 2026-09-01 |
  | `grouping_by(classifier, map_factory, downstream)` | `f6406fe` | 2026-09-01 |
  | `nulls_first()` / `nulls_last()` | `8cdcf31` | 2026-09-01 |
  | `comparing(f, keyComparator)` / `thenComparing(f, keyComparator)` | `31860e6` | 2026-09-01 |

  The last row closed **past** parity rather than to it: both overloads were
  struck-through *skips* at the time of the audit, decided against, and were
  then implemented anyway. So the five-item list was the floor, not the ceiling.

  **Counted, not asserted.** Every row in README's three tables is now either
  `x` or struck-through; none is in the third state the audit introduced for a
  genuine gap. Machine count at `3be5ed1`: `Stream` + `BaseStream` 37 / 11 / 0,
  `Collectors` 24 / 3 / 0 (plus the `x/-` `Characteristics` row), `Comparator`
  6 / 6 / 0 — 67 implemented, 20 skipped, **0 gaps**. The check is mechanical
  because `enumerate-java-8-parity-gaps` made the tables *total over Java 8's
  surface* and gave absence its own row state; that is what turns "are we done"
  from a judgement into a `grep`. A Java 8 method with no row remains a defect
  in the table, so a rediscovered gap is a documentation bug to fix in place,
  not a reopening of this entry.

  **Three documents disagreed with the code for four days** — the **Now**
  queue, the Java 9 **Later** row, and the closing paragraphs of the audit's own
  Done entry all still described five open gaps while four of them had shipped
  by 2026-09-01. All three are corrected here: the two live pointers are
  rewritten outright, and the Done entry keeps its text — it is history, and
  accurate as of its date — with dated annotations marking in place the three
  claims later events falsified. The lesson
  is the one the audit itself drew one level up: a list of open items written in
  prose decays the moment an item lands, which is exactly why the *table* —
  with a row state for absence — is the artifact that answers this question,
  and the roadmap is not.

  **Java 9 is unaffected by this and stays in Later.** Closing Java 8 removes
  the *gate* README put in front of Java 9; it does not supply the decision
  that row is actually waiting on. See that row for the six additions and what
  each would cost.

- **`_guarded()`'s flag argument: asked, and answered in the affirmative**
  (closed 2026-09-05; filed 2026-09-02 by the
  `sort-mixed-lane-by-successive-passes` read, never scaffolded). Moved here
  from **Now**, which is a pool of work available to start, and this is not
  work any more. It is recorded as **closed rather than moot**, because
  "the code was deleted" undersells what happened to it.

  **The split it asked for is what the replacement does.** The finding wanted
  one thing: `if window is None`, re-asked on every element to guard two
  nearly-disjoint loop bodies, should become two generators each showing one
  concern. `_fork_join_batches()` (`execution.py`) asks it once per *call* —
  `through = _fork_join_ordered_batches if ordered else
  _fork_join_unordered_batches` — and the two bodies are separate top-level
  generators, one carrying the round protocol and one the sliding window. The
  branch did not survive into the per-element path in another form; it moved to
  dispatch, which is the outcome the finding argued for.

  **Its own gate was applied, and passed.** The item named an honest objection
  against itself: splitting duplicates the shared pull and the `finally` close,
  and `extract-racing-task-lifecycle` (**Done**, 2026-09-02) is the precedent
  saying only the genuinely identical parts belong together. That test was run.
  `_fork_join_batches()` keeps exactly the identical scaffolding shared — the
  state-map build, and the single `aiter(source)` under `maybe_aclosing()` —
  while the two loops stay apart. So the finding's stated decision procedure
  reached the opposite of the outcome its own text predicted ("it may well
  decide against it"), by way of a change that was not about it at all.

  **What is genuinely gone:** `_guarded()` and `race_through()` are deleted
  along with the racing executor (`fork-join-executor-and-spliterator`,
  2026-09-04). Nine comments in `src/` still name `RACING`, and two name
  `_race_through()` — `execution.py:451` and `:483` — a function that exists
  nowhere in the repo. Left deliberately: both spell out the reason they invoke
  rather than merely pointing at it, so a reader who greps and finds nothing has
  still been told what they needed. Filed here as a known, priced residue rather
  than as an open item.

  The finding follows as originally written, with its **Now**-bucket preamble
  kept — "Not claimed", "Ranked as listed" — since that is what it said at
  the time; the only edit is the removal of its superseded "Moot as of" header,
  which this entry replaces.

  One smaller finding from the same pass over `src/`, recorded rather than
  scaffolded because the sort item was the one worth taking first. Not claimed.
  **Ranked as listed.** Checked against **Done** before being filed here: it is
  not a re-proposal of anything in the rejection log.

  **The finding, as filed 2026-09-02.** `_guarded()` re-asks a question
  decided at composition, once per pull.

  `if window is None` is checked on every element, guarding two nearly-disjoint
  loop bodies inside one `while True`, with only the `finally` genuinely shared.
  The answer never changes for the life of the generator: `race_through()` passes
  a window exactly on the split path and never on the other, so the branch is
  settled before the first pull. It is the flag-argument shape, and splitting it
  into two generators would let each show one concern — the windowed one
  carrying the slot protocol and the index assignment, the plain one being
  what it was before delivery ordering landed.

  *The gate, and the honest objection.* This is a per-element path, so the `+10%`
  threshold applies — but in the favourable direction for once, since the
  branch is removed rather than added, which puts it in the same family as
  `sort-mixed-lane-by-successive-passes` rather than in the family of the
  rejections. The objection is real and should be priced before starting: it
  *duplicates* the shared-lock pull and the `finally` close, and unifying exactly
  that kind of scaffolding is what `extract-racing-task-lifecycle` (**Done**,
  2026-09-02) set out to do. That change's own reasoning is the precedent to read
  first — it kept arming and teardown shared while leaving the two merge loops
  apart, on the grounds that only the identical parts belong together. The same
  test applied here is what decides this item, and it may well decide against it.

- **`make-combiners-live`** (2026-09-04) — the last of the three items the
  free-threading sequence (`add-free-threaded-ci-leg` ->
  `fork-join-executor-and-spliterator` -> this) was for. Both combiners are
  live: `collect(supplier, accumulator, combiner)`'s parameter now runs under
  `.parallel()`, and `Stream.reduce(identity, accumulator, combiner)` — Java's
  third `reduce` overload — is added. `_ForkJoin.value()` gained a second,
  conditional override alongside `_Sequential.value()`'s fused push: where a
  terminal declares the new partition protocol (`sink-protocol`) and nothing
  in the chain needs a global view, each batch accumulates into its own peer
  container on its own thread and the peers merge into the terminal by left
  fold in batch order (`parallel-reduction`, the new capability governing the
  merge rule and the caller contract on `combiner`/`identity`). Fifteen
  built-in collectors gained a combiner — leaf where the merge is associative
  over the accumulation type (`to_list`, `to_set`, `counting`,
  `summing_int`/`long`, `summarizing_int`/`long`, `min_by`/`max_by`,
  `reducing`, the two-argument `to_map`, `joining`, `to_collection`), derived
  from downstream for the four composing collectors
  (`grouping_by`/`partitioning_by`/`mapping`/`collecting_and_then`). The
  float-accumulating family and the three-argument `to_map` permanently
  decline one, for reasons stated in each capability's own delta spec.

  The three findings from the 2026-09-01 exploration that first scoped this
  (recorded when the item moved to **Later**, then **Now**) resolved as
  follows. **(a) held as reasoned**: the combiner is the caller's declaration
  of associativity, and the only channel for it — implemented as the
  `parallel-reduction` capability's caller-contract requirement, unchecked by
  the library, matching Java. **(b) is now spent, not merely resolved** — kept
  here rather than deleted so the reasoning stays findable: it argued Java's
  associativity-alone combining now transfers because `spliterator()`'s
  batches are contiguous where the old racing executor's stolen partitions
  interleaved. That objection is gone and stays gone; nothing in this change
  reopened it, and no future change should need to re-derive it — cite this
  entry rather than re-deriving (b) from scratch. **(c)'s
  `unordered()`-only fallback was correctly never taken**: the shipped design
  partitions independent of `unordered()` (`parallel-reduction`'s "An
  unordered pipeline still merges in order" requirement is the direct
  statement of why) — the alternative (c) considered would have demanded
  commutativity, which no caller supplying a combiner has asserted.

  **(d)'s measured gap closed, from 0.98x/0.99x to 3.90x/3.89x** (task 7.1,
  `benchmark-findings.md` in the archived change — GIL-enabled build; no
  free-threaded leg run for this change). The ceiling sits around 4x
  (`WORKERS`), not the triple-digit speedups the chain-only and trivial-
  collector rows reach, because a partitioning terminal's own accumulation is
  necessarily sequential *within* a batch (a terminal's `accept()` is not
  safe to call concurrently) — only cross-batch, thread-level concurrency
  applies to the classifier sitting in a collector's accumulator, where a
  chain-side mapper also gets intra-batch `gather()` concurrency.

  **(e) predicted right that the naive "easy collectors" scoping was
  backwards, and wrong about what task 7.2 would find for them.** (e)'s claim
  that partitioning "gains nothing" for `to_list`/`to_set`/`counting` was
  about the accumulation work itself being trivial — true, and the composing-
  collector derivation did make scoping the *hard* ones (the ones carrying a
  user callable) cheap, as (e) argued. What (e) did not predict: task 7.2
  measured the combinable path for these cheap collectors *faster* than a
  hand-built no-combiner equivalent (`to_list()` ~19ms faster, `counting()`
  ~9ms faster than `count()`, at `n=8192`), not merely neutral — the
  partitioned path accumulates directly per batch with nothing buffered
  between a batch's chain output and its peer container, where the
  non-partitioning path still composes through `elements()`'s `AsyncGenerator`
  layer. No collector's combiner was removed on task 7.2's "measurably costs
  more" test; none measured a loss.

  design.md's Open Question — a partition per *worker* rather than per
  *batch* — stays open and unmeasured (task 7.4): the merge did not dominate
  for either cheap collector measured, so there was nothing to weigh it
  against.

  A real regression was caught and fixed before this reached review, not
  after: the first version of the partitioned batch runner pushed a batch's
  elements through the chain *sequentially* into the peer sink, rather than
  reusing `_run_batch_async()`'s existing per-element `gather()`. That
  regressed a slow-mapper-declared-before-`.parallel()` benchmark by ~4x
  (`test_parallel.py::test_parallel_applies_to_ops_declared_before_it`, 8
  elements at 0.1s each: 0.1s expected under batched concurrency, 0.4s
  measured under the sequential-push mistake) before `_run_partition_sync()`
  was rewritten to race the chain first and fold only the already-transformed
  outputs sequentially. A second, quieter one: `CollectorSink`/`ReduceSink`
  reclassifying their own accumulator's awaitability once per **batch**
  (`new_partition()` calling `__init__` without carrying the already-computed
  `is_async` forward) rather than once per composition — caught by
  `test_classification_is_not_repeated_per_element_under_fork_join` (8 calls
  vs. 3 expected), the same `callable-dispatch` requirement the *previous*
  archived change's near-miss violated for a different reason (a sink rebuilt
  per element there; a sink rebuilt per batch here) — see that entry below.
  Both fixes are load-bearing for the benchmark numbers above, not
  independent cleanups.

  Giving a built-in collector a combiner also changed observable delivery
  order for `.parallel().unordered()` on the collectors that gained one: a
  partitioned merge is always in batch (encounter) order regardless of
  `unordered()` (`parallel-reduction`), so `unordered()` stopped buying back
  race-order delivery specifically for `to_list()`/`to_map()` (no merge
  function) `.collect()` calls — it still matters for `limit`/`skip`/
  `distinct` running inside the batches and for an order-blind
  short-circuiting terminal not waiting on a slow batch elsewhere. Named in
  README's Migration entry as the one place an existing call site's *result*
  can change — a caller-supplied **non-associative** `combiner` — not as a
  timing-only effect. A `None`-returning, mutate-in-place `combiner` (Java's
  `Stream.collect(Supplier, BiConsumer, BiConsumer)` convention, `list.extend`
  being Java's own example) is not in that category: `CollectorSink.merge_from()`
  reads a `None` result as "mutated in place" rather than as the new
  container, so both of Java's two combiner conventions work unchanged. Caught
  by a peer session's review before archive — the first version required a
  returning `BinaryOperator` unconditionally, silently breaking the type this
  library itself declares (`stream.py`'s `combiner: BiConsumer[R, R]`) and
  Java's own dual-convention contract, the one category CLAUDE.md's guiding
  principle treats as a defect rather than an acceptable divergence.

  See `openspec/changes/archive/2026-09-05-make-combiners-live` (`design.md`,
  `test-audit.md`, `benchmark-findings.md`).

- **`fork-join-executor-and-spliterator`** (2026-09-04) — the racing executor
  is gone. `.parallel()` now decomposes the source into contiguous batches via
  a public `Spliterator`, runs each batch's chain in a worker thread on that
  thread's own event loop, and concatenates in batch order. `execution.py`
  goes **676 -> 494 lines**: `_Window`, `_guarded()`, `_group_through()`,
  `_releasable()`, `_release_in_order()`, `_run_ordered_tail()`,
  `_racing_branches()`, `_race_through()`, `_IN_FLIGHT_PER_WORKER` and
  `_in_flight()` are all deleted, because contiguous batches never destroy
  encounter order and so nothing has to restore it. Three properties replace
  the whole apparatus, each free: `asyncio.gather()` preserves argument order
  (intra-batch), batches are contiguous and consumed in order (inter-batch),
  and batch size bounds in-flight work. `split_point()` survives — a stateful
  op still cannot run independently per batch — but the barrier it drives is
  now an ordered pass over batches that already arrive in order.

  Measured against `a872f25` on the same harness, medians of 3-5 in-process
  trials (`benchmark-findings.md` in the archived change carries the full
  table):

  | shape | old | new |
  |---|---:|---:|
  | async I/O, `.parallel()` | 3.82x | **54.00x** |
  | CPU-bound, free-threaded | — | **~2x** |
  | CPU-bound, GIL build | 0.93x | 0.95x |
  | cheap sync mapper | 0.05x | 0.05x |

  **`unordered()` narrowed, and the narrowing is not a Java-parity break.**
  Delivery-order relaxation survives but is now batch-granular rather than
  per-element, and an order-blind terminal can be delayed by its own batch's
  slowest element. Java's `BaseStream.unordered()` is documented as "may
  return itself" — a permission to disregard encounter order, never a promise
  to scramble it — so preserving order is conformant. What changed is a
  performance property, not a semantic one, and the README migration entry
  says so in that order.

  **The near-miss worth recording, and it corrects the entry below.** The
  first implementation rebuilt a sink chain per element in `_run_element()`,
  which made `is_async_callable()` run **once per element** instead of once
  per composition — 1001 calls against 3, on a 500-element two-callable
  pipeline — violating `callable-dispatch`'s "Awaitability is classified once
  per composition" with no delta written. Caught in review before archive;
  fixed by classifying once on the `Op` at construction and passing the result
  through `link()`. Worth ~18ms of an ~88ms cheap-mapper regression at n=8192.

  The entry below (2026-09-03) concluded that the only way to reintroduce this
  class of failure is "to allocate the state somewhere else deliberately,
  which is a redesign and not a slip". The redesign duly happened, and the
  reasoning was **incomplete in a specific way**: it reasoned about *where the
  state lives* and not about *how long the sink lives*. `AsyncDispatch` did
  put the state on the sink instance exactly as designed; what broke the
  guarantee was the sink's lifetime shrinking from one-per-composition to
  one-per-element. No site-level check — including the AST skeleton check that
  entry declined — would have seen it, so the decline still stands. What does
  not stand is the confidence that a redesign could not do this quietly.

  **The gate's blind spot, which is the transferable lesson.** The change's
  test audit (`test-audit.md`, 125 tests classified) asked one question: *does
  this test map to a requirement that survives?* It never asked the inverse —
  *which specs might the new implementation violate?* — and `callable-dispatch`
  was never in the blast radius because nothing in it mentions racing. Any
  future change that replaces a mechanism should run both sweeps; the combiner
  change carries the inverse sweep as its own task section.

  **Deferred, not resolved:** the `racing-encounter-order` capability keeps a
  directory name describing a retired mechanism, and `test_racing_*.py` keep
  theirs, because the openspec workflow forbids renaming a capability and
  emptying it into a new one would leave two half-specs. A known wart with an
  honest fix — a rename once the requirements settle — not an oversight.

- **`add-free-threaded-ci-leg`** (2026-09-04) — CI gains a `3.14t` leg on
  `code_check`, and the audit that made it safe to build on. Three properties
  verified and promoted from observation to spec requirement: no module-level
  mutable state anywhere in `src/`, every `ClassVar` an immutable declaration,
  and per-composition dispatch state that cannot leak. The suite passed on the
  free-threaded build **unmodified**, which is what made the sequence's premise
  credible before anything depended on it.

  `install_smoke_test` deliberately did **not** get the leg. The first draft
  said it should, reasoning that wheel tags differ and a dependency might ship
  no free-threaded wheel; both were checked and neither holds — `uv build
  --wheel` produces `py3-none-any` and `project.dependencies` is empty, so the
  leg would install a byte-identical artifact twice.

  The obligation it handed forward, and the reason it went first:
  `execution.py`'s two `asyncio.Lock` sites were correct only because one event
  loop owned every branch, and `asyncio.Lock` does not synchronise across
  threads. Fork/join discharged it with `threading.Lock`-guarded containers in
  `ops.py`.

- **The Python floor sequence: 3.10 -> 3.14** (2026-09-04) — four changes,
  `raise-python-floor-to-311` through `-314`, one minor version each. Split
  rather than batched on reviewability: each unlocks a *different* lint family
  and the last two rewrite annotations across most of `src/`, so batched, the
  one behavioural deletion would have been invisible among ~40 mechanical
  rewrites.

  | step | what it deleted |
  |---|---|
  | 3.11 | the `sys.version_info` fork in `close()`; a `PERF203` suppression ruff stops raising on 3.11+ |
  | 3.12 | PEP 695 — `class Stream[T]`, `type` aliases; unquoted `FlatMapper` via the lazy RHS |
  | 3.13 | PEP 696 — 14 `AsyncGenerator[T, None]` -> `AsyncGenerator[T]` |
  | 3.14 | PEP 649 — 17 quoted annotations unquoted, 13 in `comparator.py` |

  **The point was never the versions.** Free-threading (PEP 779) is officially
  supported only on 3.14, and it is the substrate the two changes above stand
  on. Recorded because the sequence reads as housekeeping and was not.

  Two typing features were checked against the code and **declined**, so the
  questions are not re-opened. **PEP 681 (`dataclass_transform`)** has no
  possible site: it exists for a library shipping its own dataclass-like
  decorator, and this package ships none. **PEP 646 (variadic generics)** has
  one candidate — `sort.py`'s multi-key column tuple — and it earns nothing:
  the key types are erased deliberately (`KeyExtractor` returns `Any`), the
  tuple's element types change mid-flight (`_tolerant_column()` rewrites keys
  into `(present, key)` pairs), and segment identity is decided at runtime by
  signature inspection, which no checker can follow. **PEP 696 defaults on
  `Collector[T, A, R]`** were declined too: `A` is `Any` at 28 of 45 annotation
  sites and is the parameter that wants a default, but PEP 696 defaults must be
  trailing, so only `R` can take one — and reaching `A` would mean reordering a
  public generic, a silent type-level break.

- **The per-element dispatch dance, re-examined and declined a fourth time**
  (2026-09-03) — no change directory, which is why it is recorded here. The
  six-line classification dance appears at 9 sink/generator sites and
  longhand across 9 collector boxes, and is the largest literal duplication
  in the repository. It was re-opened from a fresh angle: not another attempt
  to unify the *code* — `add-callsite-dispatch` closed that — but an attempt
  to unify the *check*, an AST-level build test asserting the sites share one
  skeleton, on the `tests/test_name_visibility.py` precedent of enforcing
  mechanically what cannot be enforced structurally. It costs nothing at
  runtime, so the benchmark objection does not reach it.

  **Declined, on a reason that is not the benchmark.** The check would assert
  a skeleton that carries no invariant. What the canonical comment in
  `callable_dispatch.py` actually warns about is *state placement* — hoisting
  the `is_async`/`checked` pair out of the per-composition body, which leaks
  classification across compositions and racing branches and violates
  `callable-dispatch`'s "Classification does not leak across compositions".
  That is the one silent failure worth a mechanical guard, and all three
  families already make it unexpressible:

  | Family | State lives on | Allocated once per |
  |---|---|---|
  | 8 sink sites | the sink instance, via `AsyncDispatch._init_dispatch` | sink chain (`op.link()`) |
  | 9 collector boxes | the supplier-made container | collection (`supplier()`) |
  | `Stream.iterate()` | locals in the generator body | composition |

  So `AsyncDispatch` is not a code-sharing device — it shares three attribute
  declarations and a three-line seeder. It is what puts the state on the
  instance, and that is the whole of the guarantee. The only way to
  reintroduce the leak is to allocate the state somewhere else deliberately,
  which is a redesign and not a slip.

  The dance's remaining obligation — awaiting correctly — is already pinned
  per site: `tests/test_callable_dispatch.py` section 5.6 exists to take the
  `elif not checked` arc "at every call site, not just
  map/filter/summing_int", and `ops.py`, `terminals.py` and `collector.py`
  sit at 100% branch coverage, so every arc of every copy is exercised.

  **What this adds to the record**, since `add-callsite-dispatch`'s
  benchmark-findings.md is otherwise the whole of it: the duplication is not
  only cheap but *safe*, on an argument independent of measurement. Anyone
  re-opening this should know both halves — the runtime half is closed by
  that benchmark ("the cost of any abstraction here is not the abstraction
  versus a cheaper abstraction but the abstraction versus free"), and the
  build-time half is closed by the table above.

- **`name-by-visibility-not-underscore`** (2026-09-03) — the leading
  underscore on a module-level name in `src/snakestream` had been doing the
  work of a public-API marker in a package that has no public API to mark:
  every module below `snakestream/__init__.py` is already an implementation
  detail, so 27 names were underscored *and* imported by another module in
  the package — a contradiction in terms, worst on `ordering.py`, extracted
  three days earlier, which held `is_ordered()` bare and `_split_point()`
  underscored side by side with nothing distinguishing them but which module
  each had come from.

  **The rule, adopted:** a module-level name carries a leading underscore iff
  no other module in `src/snakestream` uses it; a name reachable only through
  a module path or the package's `__init__.py` export list is bare regardless
  of whether anything inside the package imports it; `tests/` may import
  anything, which is white-box testing and not a violation. Applied as three
  stories: **27 renames** (the contradiction above, dropped one direction),
  **8 renames the other way** (`execution.py`'s `stream_through`,
  `group_through`, `race_through`, `feed_through`, `drain`, `Sequential`,
  `Racing` and `sort.py`'s `merge_sort`, each used only in its own module and
  reachable by no caller — so the rule reads in both directions rather than
  only ever removing underscores, which is how `ordering.py` got into this
  state in the first place), and **one export removed**: `PROCESSES`, cut
  from `snakestream/__init__.py` and `stream.py`'s re-export, because it was
  never a tunable lever — `execution.py` binds `RACING` from it at import
  time, so assigning to the exported name changed nothing a pipeline did —
  and the same reasoning the `racing-encounter-order` capability already
  applies to `_IN_FLIGHT_PER_WORKER` (no public name for an import-time-bound
  constant) now applies to both. Supersedes the 2026-08-24 entry below that
  added the export.

  The decidable half of the rule — underscored-and-imported-elsewhere — is
  now enforced by `tests/test_name_visibility.py`, an AST check with no
  maintained name list to fall out of date; the other half (a bare name
  really is caller-facing) is a one-time judgment with no mechanical check,
  since there is no maintained list of caller-facing names to check it
  against without the `__init__.py`-as-boundary move this rejected.

  **Two design questions answered, so neither is re-opened:**
  Making `__init__.py` the public boundary instead — re-exporting the ~40
  caller-facing names and treating every module path as internal — was
  rejected: it cannot be enforced (nothing stops `from snakestream.collectors
  import to_list` regardless of what `__init__.py` exports), and it would
  re-break the `collector`/`collectors` split done three weeks earlier for
  the opposite reason. Ruff's `PLC2701` (import-private-name) is exactly this
  rule and was rejected for now, not permanently: it is preview-only, so
  enabling it changes the behaviour of all fifteen rule families this
  project already selects, not just the one being added; and it skips
  imports used only in annotations, which would have missed `_Aiter` — one
  of the 27. Revisit when `PLC2701` stabilises, per the `lint-rule-selection`
  capability's per-rule-exemption pattern.

  1000 tests green (997 + 3 for the new check), coverage held at the
  baseline figure exactly (98.61%, `--cov-fail-under=98`), `ruff`,
  `ruff format --check` and `ty check src` all pass. `PROCESSES` is the one
  loud break (`ImportError` at the import site); everything else is
  caller-invisible by construction — same objects, same `is` comparisons,
  same call sites, resolved at import time.

  **One design-doc claim, priced during implementation and found not to
  hold, recorded so it is not re-asserted:** the design took `_UNSET` -> 
  `UNSET` as, independent of the rule, "a small correctness win" because the
  sentinel is a public factory argument's default (`reducing(identity=_UNSET,
  ...)`) and so "already rendered to users by `help()`". Checked against both
  `inspect.signature()` and `pydoc.render_doc()`, before and after the
  rename: both show the sentinel's raw `object()` repr (`<object object at
  0x...>`) in either case, never the variable name that held it at
  definition. The rename is still correct — `UNSET` is genuinely
  cross-module and the rule requires it bare regardless — but the
  independent correctness win the design claimed for it does not exist.

- **`extract-encounter-order-model`** (2026-09-03) — one concept, the
  encounter-order model, was split across two modules that were each about
  something else: `Ordering` and `is_ordered()` lived in `sink.py` (subject:
  the push protocol), `OrderDemand` and `_split_point()` lived in
  `execution.py` (subject: how a chain runs), and both placements were
  justified in-source by import topology rather than by concern — each landed
  in the deepest module its callers could already reach. The four now live
  together in a new `src/snakestream/ordering.py`, which `sink.py` and
  `execution.py` import from. A pure module-level move: the same objects, the
  same `is` comparisons, the same call sites, resolved at import time. No
  behaviour changed, no benchmark was owed (design decision 5, the same
  once-per-composition/once-per-terminal argument
  `collapse-unseeded-accumulation-rule` made), and no spec delta
  (`skip_specs: true`) — no capability under `openspec/specs/` names a module
  path for any of the four symbols.

  This is the roadmap's first **Done** entry that is a module-boundary move
  rather than a duplication collapse — the prior five per-element rejections
  and the two prior collapses were all about a rule or a hook stated more than
  once, not about where something lives.

  **Two consolidations were priced and declined, recorded so neither is
  re-derived:** folding the pair down into `sink.py` was rejected on the
  concern, not the graph — it would add a *terminal-operation policy* enum
  (`OrderDemand`, declared at a `Stream` terminal call site, not by any sink)
  to a module whose subject is `begin`/`accept`/`end`, worsening the exact
  problem being fixed. Folding the pair up into `execution.py` was rejected on
  the graph, not on preference — `ops.py` and `sink.py` both need `Ordering`
  and neither may import `execution.py`, which imports `sink.py`; that
  direction is an actual cycle, not a judgement call.

  **Renamed by `name-by-visibility-not-underscore` (2026-09-03, below):**
  `_split_point()` is now bare `split_point()` — the one holdout this entry
  left underscored beside bare `is_ordered()` in the same file, closed once
  that change's build-time check existed to enforce it either way.

- **`collapse-unseeded-accumulation-rule`** (2026-09-03) — the "an accumulation
  that never saw an element finishes as `None`" rule, previously stated five
  times with no site referencing another (`_ReduceSink._finish`,
  `_MinMaxSink._finish` and `_FindSink._finish` in `terminals.py`; `_extremum()`
  and `reducing()`'s `_finish` closures in `collectors.py`), now lives once as
  `_unseeded()` beside `_UNSET` in `sink.py`, plus a `_UnseededSink` base
  collapsing the shared `_create_container() -> _UNSET` hook the three sinks
  also duplicated. No behaviour change and no spec delta (`skip_specs: true`) —
  every capability that specifies the empty-source result already did, and
  none of them changed.

  The roadmap's open design question — whether `TerminalSink._finish`'s default
  could carry the rule instead of a dedicated base — is answered, not left for
  a later reader: it can, but shouldn't, because most `TerminalSink` subclasses
  (`_CountSink`, `_ForEachSink`, `_MatchSink`, `_CollectorSink`,
  `GeneratorBridgeSink`) can never hold `_UNSET`, and a universal default would
  assert the rule on all of them regardless (design Decision 1).

  It also takes a documented exception to the repository's recorded preference
  against thin helpers (`_checked()` in `sort.py`, `ComparatorContractException`
  are that preference applied): `_unseeded()` is a free function wrapping a
  one-line check, which the preference says to inline. Kept anyway because no
  other mechanism reaches all five sites — `collectors.py`'s two are closures
  over dataclass boxes, not sinks, so `_UnseededSink` cannot reach them, and
  without the function the collapse would be three sites out of five, leaving
  the worse half of the problem (a rule stated in two separate modules) exactly
  as it was (design Decision 3).

  **A fresh finding surfaced by this change's exploration, priced and
  declined, recorded so it is not re-derived:** `_sort_by_key`'s
  `len(columns) == 1` lane is character-for-character the general lane at
  `last = 0` — verified identical on 8,000 randomized cases, including ties
  and null-tolerant `(present, key)` tuples, both directions. Collapsing it
  costs ~0.2 us/sort of fixed `zip(*columns)` overhead on the lane every plain
  `comparing()` call takes: +18.6% / +18.8% at n=4, noise-dominated by
  n=20,000. Declined on measurement, not available work.

  **Renamed by `name-by-visibility-not-underscore` (2026-09-03, below):**
  `_UNSET` -> `UNSET`, `_unseeded()` -> `unseeded()`, `_UnseededSink` ->
  `UnseededSink`, `_ReduceSink`/`_MinMaxSink`/`_FindSink` -> bare — every name
  this entry introduced or read from was underscored while being imported by
  another module in the package, the exact shape that change's rule forbids.
  `_CountSink`/`_ForEachSink`/`_MatchSink`/`_CollectorSink` (named above as
  never holding `UNSET`) are bare now too, for the same reason, unrelated to
  this rule's Decision 1.

- **`sort-mixed-lane-by-successive-passes`** (2026-09-02) — `_sort_by_key()`'s
  mixed-direction lane was the only place left in the sort where a comparison
  ran in Python rather than in C: a chain whose segments disagreed on direction
  wrapped its descending columns in `_Descending`, whose `__lt__` cost a Python
  frame once per pair the earlier columns tied on. CPython's own guarantee
  removes the wrapper — sorts are stable, `reverse=True` included, so a series
  of stable passes least-significant-column-first *is* a lexicographic ordering
  with a direction per column. Three lanes collapsed to one loop, `_Descending`
  was deleted, and every comparison returned to C.

  *The gate was met, in advance*, and this one was not the usual shape: the
  measurement was banked in the change's design.md, and the per-element path
  got *cheaper* rather than being asked to absorb an abstraction. 20,000 rows,
  best of 11, output asserted element-identical including tie order — mixed
  **6.8x / 4.9x / 4.5x** at k=2/4/8, uniform **1.39x / 1.22x** at k=2/3. Also
  measured on distinct-key input, where the tuple lanes short-circuit at their
  best: mixed still 3.45x / 2.66x. Reproduced on the shipping machine at a lower
  magnitude but the same shape — mixed 6.0x/3.83x/2.81x, uniform crossover
  still between k=4 and k=5 — machine-to-machine variance, not a regression
  from the design's figures.

  *What it costs, and where.* Uniform chains cross over between four and five
  segments — **0.93x at k=5, 0.68x at k=8** — because k passes of C comparison
  eventually lose to one short-circuiting tuple comparison. Taken deliberately
  (design.md Decision 2): confining the rewrite to the mixed lane would have
  been faster on long uniform chains but would have made an *observable*
  behaviour lane-dependent, since sorting every column in full is what makes a
  segment's incomparable keys raise unconditionally rather than only where an
  earlier segment ties. One path, one rule. It carries the one behavioural
  delta in the change — `comparator-chaining`'s "Keys within a segment must be
  mutually comparable" strengthened to make the raise unconditional, synced to
  the main spec at archive — so unlike its neighbours here it was not
  `skip_specs`.

- **`take-window-slots-atomically`** (2026-09-02, shipped in `79e258f`) —
  moved here 2026-09-02 from **Now**, where the change's own commit had left it
  described as "scaffolded" although that same commit implemented and archived
  it. `_Window` and `_guarded()` hand-rolled a counting semaphore out of a
  counter and an `asyncio.Event`, and an `Event` cannot *hold* a slot: it only
  broadcasts that one may exist. So a branch that waited for room had to ask
  again after taking the lock, and that re-check was what forced the
  doubly-nested `while True`, the `clear()`/`wait()` protocol and a barging
  window with a regression test of its own. A synchronous `take()` — atomic
  because it contains no `await`, so nothing runs between its check and its
  increment — closed the window instead of compensating for it, and collapsed
  the arm to one loop level.

  *The gate was met, in advance.* It sits on the per-element path of the
  windowed (barrier) arm, so the `collapse-terminal-collector-duplication`
  `+10%` ns/element threshold applied; the measurement was banked in the
  change's design.md rather than left for whoever started it. Three interleaved
  runs, ordered delivery, min/median: `take()` at +1.2%/+0.3%, +0.4%/+0.9%,
  −0.0%/−1.2% — straddling zero.

  **`asyncio.Semaphore` itself is the measured rejection**, and it belongs in
  this log rather than only in the change: it is exactly the missing primitive by
  contract, and it cost **+5.7%/+7.3%, +3.9%/+6.0%, +6.4%/+5.6%** on the same
  three runs, positive in all six statistics and absent from the order-blind path
  it does not touch. `acquire()` is an `async def`, so it allocates a coroutine
  frame per pull even on CPython's non-suspending fast path. Same family as
  `add-callsite-dispatch`, `Sequential.value()`'s existence and the rejected
  `merge()` generator — **abstraction against free, not abstraction against
  cheaper abstraction** — and the first of them where the abstraction being
  priced is a standard-library one. Do not re-propose the semaphore without new
  evidence.

  *What this is not.* It is not the roadmap's "Bound speculation separately
  from read-ahead" (in **Later** when this was written; **Now** since
  2026-09-05), which changes what the bound bounds. This changes no behaviour at
  all: same value, same scaling, same fixedness for a run, `skip_specs: true`.
  The two are independent and neither blocks the other.

- **`collapse-sort-decorate-lanes`** (2026-09-02) — closes **Next**'s former
  item 3. `sort.py`'s decorate-sort-undecorate was written once per lane
  rather than once: `_column()` re-interleaved gathered keys against `None`
  three times, carrying `trial_i` and two `i != trial_i` comprehensions purely
  to skip recomputing a trial call's own result, and `_sort_by_key()` had four
  `sorted(zip(rows, arr, strict=True), key=lambda pair: pair[0], ...)` call
  sites and two identical undecorate returns. Both run once per segment or
  once per `sorted()` call, never once per element, so — unlike every other
  duplication in this neighbourhood — no `+10%` gate applied to either
  collapse.

  **`_column()`:** extracting the non-`None` elements into a `present` list
  first turns the sync trial into `results[0]`, and `trial_i` plus both
  `i != trial_i` filters have nothing left to guard; one `_interleave(arr,
  values)` helper now serves all three return paths. The invocation-count
  claim the rewrite rests on — every path calls the extractor exactly once
  per non-`None` element, the sync-that-lied path's trial element included —
  was checked directly with a counting extractor across all three paths
  before being trusted.

  **`_sort_by_key()`:** the `len(segments) == 1` fan-out branch now decides
  only the fan-out (`columns = [await _segment_column(...)]` vs. the existing
  `asyncio.gather`); a `len(columns) == 1` lane below it handles the
  no-tuple-build question separately. All four lanes reduce to deriving
  `(rows, reverse)` and falling through to one `sorted(zip(rows, arr,
  strict=True), key=itemgetter(0), reverse=reverse)` and one undecorate. The
  three measured claims in its docstring survive structurally, verified
  against the shipped code rather than re-measured: the single-segment lane
  binds `rows` to the column itself (no `tuple(...)`), the uniform lane
  reaches `sorted(reverse=...)` directly (CPython's strong stability, not a
  post-hoc reversal), and the mixed lane still wraps only descending columns
  in `_Descending`.

  **`operator.itemgetter(0)` replaces `lambda pair: pair[0]`** in the
  now-single `sorted()` call — a C callable in place of a Python frame, on a
  key invoked once per element by the sort. Python 3.14.5, 20,000 elements,
  interleaved per round to remove cross-invocation drift, best of 7, three
  independent runs:

  | shape | delta (`itemgetter` vs. `lambda`) |
  |---|---|
  | 1 segment, scalar keys | −12.4% / −19.3% / −20.9% |
  | 2 segments, tuple keys | −3.6% / −7.7% / −5.0% |

  Consistently negative on both shapes across all three runs, at or past the
  exploration's −10% / −6% figures. **Three alternatives priced and
  declined, recorded so none is re-derived:** `(key, index)` decoration with
  no `key=` at all — plain tuple comparison, zero Python-level key calls —
  measured **worse**, 5.71 ms against 3.27 ms, because the tuple comparison
  costs more than the key calls it saves, and it would additionally need a
  negated index under `reverse=True` to keep ties in encounter order.
  `sorted(range(len(arr)), key=keys.__getitem__)` over indices measured
  2.97 ms, a tie with `itemgetter` within noise, and it forces the
  multi-segment lanes to materialise their zipped rows as a list to stay
  indexable — no clearer, no faster. Folding the single-segment fan-out into
  the general `asyncio.gather(...)` would remove a branch but costs 9.1 us
  against 192 ns for a direct `await`, once per sort — roughly 4x the entire
  cost of sorting five elements, and small sorts are the common case for a
  tie-break chain — so the fan-out branch stays, now deciding only the
  fan-out rather than the fan-out and the lane and the undecorate together.

  **`comparator.py`'s segment-sign 2x2 — the remaining item from the same
  read, still in Next — was deliberately left out of this change**, not
  overlooked: it sits on a per-element path (`min()`/`max()`,
  `min_by()`/`max_by()`, one comparison per element) under the
  `collapse-terminal-collector-duplication` `+10%` ns/element gate, and
  bundling it would put a measured trade-off inside a change that otherwise
  has none. It stays queued on its own gate.

  988 tests green, unchanged from before — `git diff --stat tests/` empty, no
  test file, name or import touched (`sort.py` has no reachable test import;
  all coverage runs through `Stream.sorted()`). Coverage 98.62%; `sort.py`
  shrank from 117 to 111 statements and 40 to 38 branches, 0 missed and 100%
  both before and after — the five removed branches were fully covered, not
  under-tested, so no arm went silently unreachable. No README migration-log
  entry, and that absence is a claim: nothing a caller can observe changed.
  `skip_specs: true`.

- **`collapse-mutable-reduction-onto-collector`** (2026-09-02) —
  `_MutableReductionSink` (`terminals.py`) and `_CollectorSink`
  (`collector.py`) were the same bases, the same `AsyncDispatch` triple and a
  byte-identical `accept()`, differing only in where the container came from.
  `collect()`'s three-argument branch now builds a
  `Collector(supplier, accumulator, combiner)` and drives it through the
  existing `_CollectorSink` path the single-argument branch already used;
  `_MutableReductionSink` and `Stream._collect_mutable()` are deleted, along
  with `terminals.py`'s now-unused `BiConsumer` import and `stream.py`'s
  now-unused `_maybe_await` import (`TerminalSink.begin()` already routes
  `_create_container()` through `_maybe_await`, so the supplier needs no
  separate awaiting once it lives on a `Collector`). `ty check` stayed clean
  without the `cast` design.md Decision 5 anticipated needing between
  `collect()`'s `BiConsumer[R,R]` combiner and `Collector.__init__`'s
  `Combiner[A] | None` — the mismatch `ty` was expected to reject did not
  materialize, so none was added, per the task's own "do not add the cast
  preemptively."

  **What makes this different from `collapse-terminal-collector-duplication`
  (2026-08-21, below), which rejected the same *shape* of collapse for
  `count()`, `min()`/`max()` and `reduce()`:** that change's three sinks have
  no `Collector` counterpart to fold onto — `counting()`/`min_by()`/
  `reducing()` keep their own per-collection dispatch state on a
  supplier-made box and wrap the user's callable in their own
  `async def _accumulate`, so routing through them adds a coroutine frame and
  an attribute hop per element that the dedicated sinks don't pay. The
  three-argument `collect()` form has neither box nor wrapper: its
  `accumulator` already *is* a `Collector`'s accumulator, `(container,
  element)`, dispatched by the same `AsyncDispatch` attributes on the same
  sink shape `_MutableReductionSink.accept()` ran. Counterpart versus no
  counterpart, box versus no box — that is the distinction, not the
  conclusion "collector-routing terminals is now safe to retry." Anyone
  reading this as licence to re-open `_CountSink`, `_ReduceSink` or
  `_MinMaxSink` is reading it backwards; those remain a measured, deliberately
  rejected trade.

  **Measured against the `collapse-terminal-collector-duplication` gate**
  (+10% ns/element on the sync variant, Python 3.14.5, 20,000 elements,
  interleaved round-robin, best of 3 across 10 rounds), pre-change baseline
  (`_MutableReductionSink` via the public three-argument `collect()`, recorded
  before any code changed) against the shipped code (the same three-argument
  `collect()` call, now routed through `_CollectorSink`), ns/element:

  | variant | baseline | shipped | delta |
  |---|---|---|---|
  | sync accumulator | 321.2 / 327.9 / 341.9 | 299.2 / 320.4 / 325.8 | −6.9% / −2.3% / −4.7% |
  | async accumulator | 390.8 / 427.9 / 401.6 | 417.9 / 409.9 / 433.0 | +6.9% / −4.2% / +7.8% |

  Every sync delta negative and every figure inside the ~10% run-to-run noise
  this harness has shown before; the gate is judged on the sync median
  (−2.3%), well under +10%, so the change **shipped rather than reverted** —
  the branch design.md's Decision 4 risk did not take.

  988 tests green, unchanged from before — `git diff --stat tests/` empty, no
  test file, name or import touched (the only test naming the deleted path,
  `test_callable_dispatch.py::test_collect_mutable_sync_call_returning_coroutine`,
  exercises the public three-argument `collect()` and passed unedited).
  Coverage 98.62%; `terminals.py` shrank from 129 to 113 statements, 0 missed
  before and after, 100% both times — the sink it lost was fully covered, not
  under-tested. No README migration entry, and that absence is a claim: no
  signature, return type, parity checkmark or observable behaviour changed.
  `skip_specs: true`.

- **`extract-racing-task-lifecycle`** (2026-09-02) — the `FIRST_COMPLETED`
  merge over N branches' `anext()` existed twice, verbatim, in
  `race_through()` and `_release_in_order()`, and the module docstring's
  "four primitives do the work" did not name it because it had been copied
  rather than extracted. Both docstrings already admitted it in prose —
  *"the same `FIRST_COMPLETED` merge `race_through()` runs, with a buffer in
  front of the yield"* and *"same clean-up as `race_through()`'s, plus closing
  the branches"* — which is a function signature written as a comment.

  **What shipped is the smaller of two extractions, and the choice was
  measured.** `_racing_branches()` is an `@asynccontextmanager` beside
  `_maybe_aclosing()` owning the arming and the teardown — twelve of the twenty
  duplicated lines. The eight-line `while`/`for` body stays in both callers,
  because that is the half that genuinely differs: one yields a completed
  result as it stands, the other buffers it by source index.

  **Rejected: extracting the whole merge as a `merge()` async generator.** It
  removes all twenty lines and costs one async-generator hop per element on the
  racing path. Python 3.14.5, 20,000 elements, `map(x + 1)`, 4 workers, all
  variants draining into the same `_CountSink`, ten interleaved samples,
  µs/element:

  | variant | order-blind, min / median | ordered delivery, min / median |
  |---|---|---|
  | baseline | 7.12 / 7.40 | 9.42 / 9.62 |
  | `merge()` generator | 7.25 / 7.70 — **+2.0% / +4.1%** | 9.79 / 10.05 — **+3.9% / +4.5%** |
  | `@asynccontextmanager` | 7.07 / 7.47 — −0.7% / +0.9% | 9.41 / 9.55 — −0.1% / −0.7% |

  ~4%, consistent across both pipeline shapes and both statistics, appearing
  identically whether the merge feeds a yield or a reorder buffer — which is
  what a per-element charge looks like and what a per-composition one does not.
  About a fifth of the reordering half of the barrier again (0.68 µs/element,
  per `race_through()`'s docstring), so not lost in the machinery's own noise.
  Same family of finding as `add-callsite-dispatch` and as
  `Sequential.value()`'s existence: **a generator hop on a per-element path is
  never free here, and the comparison is abstraction against free rather than
  abstraction against cheaper abstraction.** Do not re-propose without new
  evidence.

  **Two traps in measuring this path, both of which produced a wrong answer
  first.** Block-sequential timings drift by more than the effect: a first pass
  reported the `@asynccontextmanager` variant at +3.3%, which is impossible for
  an extraction that runs once per composition, and interleaving round-robin
  dissolved it. And when the verification benchmark loaded the pre-change module
  alongside the shipped one to interleave them, it fed the shipped
  `OrderDemand.IF_ORDERED` to *both* — `_split_point()` compares with `is`, the
  copied module defines its own enum, so the pre-change side silently took the
  no-split path and read as 34% *faster* until its ordered figure was noticed
  matching its own order-blind one. Anyone re-measuring across two copies of
  `execution.py` must give each its own enum members.

  **The one behaviour settled rather than preserved: both merges now close
  their branches.** The barrier did and the plain merge did not, on a reason
  that names the window — a branch parked on a full window has a finally of its
  own to run and no outstanding `anext()` for a cancel to reach. That does not
  extend to the unwindowed path, but nothing established the converse either,
  and `aclose()` on an exhausted generator is a no-op so unifying cannot
  double-close. **No spec changed**: `racing-encounter-order` already required
  the shared source be closed exactly as it is without a barrier, with two
  equal-close-count scenarios; this makes one mechanism true where two
  previously happened to agree, and those scenarios were the regression gate.

  988 tests green, unchanged from before — `git diff --stat tests/` empty, no
  test file, name or import touched. Coverage 98.64%; `execution.py` lost one
  statement and two branch arcs (three `for` loops across two `finally` blocks
  became two in one), missed statements 0 before and after, and its two partial
  branches are the same pre-existing site shifted by the added helper. No
  README migration entry, and that absence is a claim: nothing a caller can
  observe changed. `skip_specs: true`.

- **`bound-in-flight-work-per-worker`** (2026-09-01) — item 3, the last of the
  four, and **it closed the other way from how the item said it would**. The
  item read "its answer flipped to 'export it'"; this change renames the
  constant and declines the export.

  **The correction is that the obligation the item cited was already
  discharged.** Item 3 argued that `_READ_AHEAD` had become public because it
  bounds something a caller can count — how many times a mapper runs under a
  parallel `find_first()` — and so "an observable effect a spec has to state".
  The spec already stated it. `collapse-find-first-onto-barrier` wrote
  `stream-find-first`'s "find_first() may invoke a chain's callables more than
  once" in the same change that created the behaviour, **including both
  regimes** — the worker count under uniform latency, the window otherwise.
  Item 3 was written as if that requirement did not exist. Observable is not
  the same as public: `find_any()`'s choice of element is observable and
  spec'd, and nothing about it is exported.

  **What shipped instead of an export.** `_READ_AHEAD` became
  `_IN_FLIGHT_PER_WORKER = 4` plus `_in_flight(workers)`, so the bound scales
  with the branch count — the tuning curve knees at *one slot per worker*, a
  fact the old comment recorded and then contradicted by hardcoding 16. The
  effective bound at the default worker count is unchanged (4 × 4 = 16) and no
  behaviour a caller can observe changed, so there is **no migration-log
  entry**; that absence is a claim, not an oversight. `_Window` now takes its
  size at construction rather than reading a module global on every pull, which
  is what makes "fixed for the duration of a run" true in the code.

  **The rename stopped at the code, and that is the second correction.** The
  item wanted the name to cover all three things the constant bounds and
  guessed "the window" might be as close as it gets. But the *requirement* is
  about elements pulled but not released, which **is** read-ahead, accurately;
  what bounds three things is the constant. So `racing-encounter-order` keeps
  the word and gained two clauses instead — the window scales with the branch
  count, and its size is fixed for a run — plus a new requirement that the
  bound is **not** public, naming `unordered()`/`sequential()` as the levers a
  caller gets. That requirement is the change's actual product: it makes
  retuning the value a measurement rather than a compatibility question, which
  is what "revisit on a concrete report" never managed to say bindingly.

  Queued a follow-up rather than folding it in — filed in **Now** → **Queued
  changes** and moved to **Later** the same day, once it was clear the blocker
  is a decision and not effort: one counter serves memory, latency and
  speculation, and under a short-circuiting terminal it bounds the wrong one.

- **`collapse-find-first-onto-barrier`** and
  **`collapse-for-each-ordered-onto-barrier`** (2026-08-31) — item 2, landed as
  two changes because the two terminals stopped sharing a fix once
  `order-racing-delivery` shipped. Both had named `SEQUENTIAL` at their own call
  site to buy encounter order; both now declare a demand and keep the caller's
  executor. `for_each_ordered()` was a four-line deletion whose condition
  `_split_point()` already computed. `find_first()` needed the terminal's
  declaration widened from a bool to `OrderDemand` — `NONE`/`IF_ORDERED`/`ALWAYS`
  — which makes clause 3 the two op clauses again one level up: `Ordering.SET`
  is to `ALWAYS` what `order_sensitive` is to `IF_ORDERED`.

  **The parity defect was that `find_first()` was a hidden mode switch**, the
  only terminal that discarded `.parallel()` while `is_parallel()` still
  reported `True`. Java's `FindTask` scans leftmost across fork-join branches;
  it does not fall back to a sequential traversal. The guarantee never changed
  and did not need to: the barrier restores encounter order on any chain,
  because `_guarded()` assigns the source index under the lock and `unordered()`
  clears the *requirement* to honour it, never the ability.

  **Three corrections this item produced, each to something previously written
  down as fact:**

  - **`_is_ordered()` and the `SEQUENTIAL` name both survive.** The "what
    disappears" list claimed three deletions; it was one, `_evaluate()`'s
    `executor` parameter. `Stream.concat()` is `_is_ordered()`'s other caller
    and names `SEQUENTIAL` on the line above. The error had been copied here
    from `CLAUDE.md`, now fixed at both sites.
  - **"racing wastes <=15 maps" had two regimes, and the common one is the
    worker count.** `find_first()` settles at the first *released group*, and no
    branch can be more than one group ahead by then, so a uniform-latency chain
    wastes `PROCESSES`. `_READ_AHEAD` is the bound only where element 0 is
    slower than what follows it. Measured: `filter`/`flat_map` 3.11x/3.21x, and
    `map` at 0.96x — **not a regression**, because the speculative maps run
    concurrently with the one that matters rather than in front of it.
  - **The empty-chain `.parallel()` cost is not the barrier and is not new.**
    `count()` declares `NONE`, takes no split, and still pays almost all of it
    (1456us against `find_first()`'s 133us on 200 elements), so it is
    `race_through()`'s branch-setup cost and has been there since delivery
    ordering landed. Recorded in `race_through()`'s docstring; no fast path,
    because a barrier-keyed one would fix nothing.

  Two silent breaks, both in README's migration log: `find_first()` stops
  overriding `unordered()` for an order-sensitive op upstream, and a chain
  callable may run for more than one element. `.sequential()` restores both.
  Also deleted a `terminal-sinks` scenario asserting an unordered parallel
  `find_first()` "behaves as `find_any()`", which had contradicted
  `stream-find-first` and the shipped code since
  `order-stateful-ops-under-racing`.

- **`mark-to-map-order-blind`** (2026-08-31) — closes the last of the seven
  questions the **Open questions needing a session** section was opened to
  carry, and **that section is now gone** rather than left standing empty; the
  queue above it is where the next open item goes.

  **The answer is two answers, because `to_map()` is two collectors behind one
  factory.** Called without `merge_function` it declares
  `Characteristics.UNORDERED`: the `dict` is a function of the element multiset
  alone — each key and value comes from one element and consults no other,
  `dict` equality ignores key order, and any multiset whose result would depend
  on order raises instead. Called with one it declares nothing, **permanently**
  and by written requirement rather than by silence, on the precedent
  `mark-order-blind-collectors` set for `summing_double()`: `merge_function` is
  caller-supplied and need not commute, and `lambda a, b: a` is the one-line
  proof. It is the first factory here whose characteristics come from its
  *arguments* rather than from its identity or a downstream's.

  **The obstacle that kept it open did not survive contact with the contract.**
  `mark-order-blind-collectors` declined to fold this in partly because the
  no-merge form raises on a duplicate key and reordering can change which key
  the message names. `UNORDERED` claims that two orderings collect to an equal
  *result*, and an exception is not a result; what a caller can act on —
  whether it raises, and the type — is order-invariant either way. Only the key
  named varies, only with two or more distinct collisions, and only under
  `RACING`, on a path where even the sequential answer was an artifact of
  ordering rather than a documented choice.

  **No benchmark was run, deliberately.** The barrier's cost is a property of
  `race_through()` and not of the collector behind it, already measured at
  1.12–1.27x on tail-latency IO. More per-element work in a collector makes the
  barrier's relative cost *smaller*, so re-measuring with a dict-building
  accumulator could only have weakened a case being made on semantics. This is
  the shape of question that a benchmark cannot settle, which is exactly why the
  section carried it separately from the parity queue.

  **`to_map()` gets the stronger guard, not the weaker one.** `counting()` and
  `to_set()` are verified by asserting the declaration plus the separately
  pinned mechanism, because no public surface distinguishes their two paths. A
  `dict` does: key iteration order follows insertion, so the order-blind path is
  verified by *observation*, and the 3-arg form is verified from the other side
  — a first-argument-winning merge must yield the encounter-order value. Both
  were mutation-checked: marking both forms fails the second, marking neither
  fails the first. `racing-encounter-order` gained the sentence that makes this
  legible — a property the declaration does not *promise* is still admissible as
  *evidence* of which path ran.

- **The stray `</content>` tag in the main specs is gone** (2026-08-31),
  resolving the repo-hygiene item **Now** carried as open question 6, with no
  change proposal: two lines, no spec text touched, 41/41 specs still
  validating. By the time anyone
  looked it was two files and not the three the item recorded —
  `stream-iterate/spec.md` and `collector-to-map/spec.md`.
  `collector-to-set/spec.md` had lost its copy without anyone noticing, because
  `mark-order-blind-collectors` rewrote that file's tail for its own reasons.

  **That is the finding worth keeping: the tag was never fixed, it was
  *overwritten*.** A defect that disappears only when something else happens to
  rewrite the same lines is one nothing was watching, which is why this one was
  rediscoverable three times. `openspec validate --specs` passes with the tag
  and passes without it — the parser ignores trailing junk — so no gate here
  would ever have caught it.

- **`implement-python-data-model`** (2026-08-31) — `Stream` implemented **no**
  dunder methods at all, so the library's own guiding principle, Java's surface
  with Python underneath, was unmet at exactly the place Python shows through.
  Adds `__aiter__`, `__enter__`/`__exit__` and `__repr__` as **parity** — Java's
  stream satisfies its language's iteration, resource and `toString` protocols
  and ours satisfied none of Python's equivalents — plus `__add__` over
  `Stream.concat` as the one **deliberate expansion**, argued as an exception
  rather than smuggled in with the others. Third of question 7's three.

  **`__bool__` raising is the member that justified the change existing.**
  `bool(Stream.empty())` was `True`, not because anyone decided it but because
  `object.__bool__` is the default and nobody overrode it, so `if stream:`
  answered a question the caller plainly meant to ask, answered it wrong, and
  said nothing. There is no correct synchronous answer to give instead, so
  refusing is the fix — the one operation this library declines that Python
  permits on every other object. The message names `count()`, `any_match()` and
  `find_any()`, because a `TypeError` that only says no leaves the caller no
  better off than the wrong `True` did.

  **The `__getitem__` finding is the one worth not rediscovering.** It is the
  only refused protocol that could have worked — `s[10:20]` is lazy and returns
  a `Stream` — and it is excluded on a mechanical hazard verified on 3.14:
  Python synthesizes an iterator from `__getitem__` when `__iter__` is absent,
  so defining it would make `for x in stream` call `stream[0]`, receive a
  `Stream`, and loop forever without ever raising. It cannot be added alone;
  `__iter__` defined-to-raise must land in the same change, never after. All six
  refusals are now **specified rather than merely absent**, which is the same
  failure mode question 5 found in README's parity tables: absence that no
  artifact could express reads as an oversight rather than a decision.

  `async with` was split off and parked in **Later** — `CloseHandler` is a sync
  no-arg callable and `close()` never awaits, so `with` is the honest protocol
  for the contract as it stands, and the async pair would be a claim about
  `stream-close-handling` rather than about two methods.

- **`derive-without-reinit`** (2026-08-31) — `_derive()` built the next stage
  with `type(self)(self._source, self._close_handlers)`, re-entering the user's
  constructor: a three-op pipeline plus one mode switch ran it **five times**.
  Now derives by `copy.copy`, so a subclass's `__init__` runs once per pipeline
  and its state is shared across stages by identity. Question 7 as filed;
  second of its three changes. **BREAKING for subclasses only.**

  **The item's leak claim was conditional, and the exploration found two larger
  problems it had not named.** With `on_close()` registered inside `__init__` —
  the idiom CLAUDE.md documents — nothing leaked: `_close_handlers` is passed by
  reference, so all five handlers landed in the same list and one `close()`
  fired all five. The shared list accidentally masked it. The leak was real only
  for a subclass overriding `close()` (measured: 3 opened, 1 closed, 2 orphans).
  Either way the **churn** was the defect regardless of the leak — five
  connections opened and one used, and perfect cleanup of four resources that
  should never have existed is still wrong.

  The problem nobody had named is **the signature contract**: passing
  `(source, close_handlers)` positionally silently required every subclass to
  accept exactly that, with an already-normalized `AsyncGenerator` first. The
  natural way to write the documented use case — `DsnStream(dsn)` acquiring a
  connection and calling `super().__init__(conn.rows())` — raised `TypeError` on
  its first intermediate op, so the documented feature was close to unwritable.
  README's own subclassing paragraph described that shape.

  **Why copying rather than Java's answer.** Java never had this bug because its
  derived stages are an internal type holding no resource and `Stream` is an
  interface nobody subclasses. This library went the other way deliberately —
  `type(self)` was there to preserve subclass identity across derivation, which
  `test_a_user_subclass_survives_a_mode_switch` pins — and once identity is the
  requirement, copying is the only way to have it without construction.

  **That test could not have caught this**, and is the third instance of the
  pattern this file keeps recording: it asserted `seq.resource == "db-handle"`
  against a string literal, pinning that the attribute *survived* rather than
  that it was the object the constructor assigned, so it passed throughout.
  Changing the one assertion to `is` turned it into a reproduction.

- **`concat-carries-characteristics`** (2026-08-31) — `Stream.concat(a, b)`
  returned a base `Stream` with an empty chain and the default executor, so it
  carried its operands' elements and close handlers and nothing else they knew
  about themselves. Java's one sentence is the whole contract: the result *"is
  ordered if both of the input streams are ordered, and parallel if either of
  the input streams is parallel"*. First of question 7's three, and the reason
  it went first: **it was wrong today with zero subclasses in play**, where the
  item that opened the session only bit a subclass the repo does not have.

  Measured before: `concat(a.parallel(), b.parallel()).is_parallel()` was
  `False`, and `concat(a.unordered(), b.unordered())` was ordered — so
  `unordered()`, the documented performance lever, was silently revoked past the
  concat boundary and the caller paid a barrier they had explicitly opted out of.

  **The two halves arrive by different mechanisms, and the asymmetry is not
  new.** Mode is a value on the stream and is assigned; ordering is positional
  and has to occupy a position, so the result seeds its chain with the stage
  `unordered()` queues. That is not a stylistic pick: `pipeline-immutability`
  forbids carrying the characteristic as state beside the chain, so a field was
  never available. It reads oddly — a chain the caller did not write — but it is
  correct in Java's own terms, `unordered()` being a pipeline stage there for
  exactly this reason.

  **BREAKING, and the silent wrong answer is why.** `concat()` now consumes both
  operands. It previously left them live over the source the concatenation also
  drew from, so `await a.collect(to_list())` returned `[1, 2, 3]` and the
  concatenation then yielded `[4, 5]` — a shortened result with no exception
  anywhere. Java raises here; `AbstractPipeline` marks the operands linked.
  `iterator()` is untouched, its non-destructive composition being a
  `stream-iterator` requirement that `collect(to_generator)` and `flat_map`
  depend on, so the invalidation belongs to `concat()`.

  One decision recorded rather than fixed: the result stays a base `Stream` even
  when both operands share a subclass. `type(a)` and `type(b)` may differ with no
  principled tie-break, a subclass constructor may want arguments `concat()`
  cannot supply, and Java returns an internal type for the same reason. It has no
  executable guard and cannot have one — nothing would make `concat()` start
  returning a subclass by accident — so the spec is the record.

- **`enumerate-java-8-parity-gaps`** (2026-08-31) — README's three parity
  tables are now **total over Java 8's surface**, and the five methods this
  library genuinely lacks are queued by name in **Now**. Closes question 5.

  **Overtaken by events 2026-09-05: all five shipped, and the queue this entry
  created in the Now bucket is retired.** See "Java 8 parity is closed" at the
  top of
  **Done** for the ledger and the count. The paragraphs below are left as
  written and are accurate as of 2026-08-31; where one asserts something a later
  event falsified, the annotation says so in place. Read the closing entry
  first — nothing here is a live pointer any more.

  **The question's own premise was the finding.** Three places in this file
  offered "the Java-8 parity gaps README still tracks as unimplemented" as a
  refill source for **Next**, and README tracked no such set. Its tables had two
  row states — `x`, and struck-through-with-a-reason — where Java's surface has
  three: a method nobody wrote a row for had no row at all, so absence was
  invisible rather than deferred. A row existed only because someone wrote one.
  That is why the refill source could be pointed at from three places without
  any of them naming a member, and why an enumeration alone would have been half
  a fix — a list in a roadmap paragraph decays the moment a method lands. The
  tables carry a third row state now, declare their own totality, and make a
  Java 8 method with no row a defect in the table rather than a silence.

  Rows added: `close()`, `on_close()`, the 3-arg `reduce`, `spliterator()`,
  `Optional`, the 4-arg `to_map`, the 3-arg `grouping_by`,
  `grouping_by_concurrent`, `to_concurrent_map`, `Collector.of`,
  `then_comparing(comparator)`, `nulls_first`/`nulls_last`, the six
  `comparingInt`-family skips, and `compare`/`equals`. Final counts in rows:
  `Stream` + `BaseStream` 35 implemented / 12 skipped / 1 gap, `Collectors`
  22 / 3 / 2, `Comparator` 3 / 8 / 2 — per Java method the last is 3 of 17,
  which is where the surface is genuinely thinnest.

  **Two documents asserted a signature that does not exist**, and both are
  corrected. The **Later** entry bundling `reduce()` and `collect()` as "both
  accept a `combiner` for Java signature parity but never invoke it", and
  `collector.py`'s `Collector` docstring repeating it, were wrong about
  `reduce()`: it has two overloads and a third positional argument is a
  `TypeError`. Only `collect()` ever grew the parity argument. That split the
  **Later** entry — `collect()`'s half keeps the real-parallelism blocker, since
  its parameter exists and would have to start doing something; `reduce()`'s
  half is gap 1, where the question is whether parity is worth a parameter that
  must be documented as inert. **The split was undone on 2026-09-01** and the
  two halves are one **Later** row again — not because this correction was
  wrong (it was not; the signature really does not exist) but because the
  question it posed got answered the other way: the parity argument is not
  worth an inert parameter, so both halves wait on the same prerequisite. The
  factual correction stands; only the bucketing it implied was reversed.

  **Four rows claimed a type this library does not have.** `find_any()`,
  `find_first()`, `max()` and `min()` were typed `Optional[T]` and described in
  Java's vocabulary ("an Optional describing…", "an empty Optional"); they
  return `T | None`, and nothing here has `is_present`/`or_else`/`if_present`.
  Almost certainly `typing.Optional` written in Java's idiom rather than a claim
  anyone defended — which is exactly why it needed correcting, since it read as
  one. `Optional` now has a struck-through row stating the skip: `is None`
  answers the membership question, the chaining half is a second fluent layer
  over a value the caller already holds, and adopting it would be a new public
  type plus a return-type break on four terminals and `reduce()`, so it wants
  its own proposal rather than a place in a queue of overload widenings.

  **The Java 9 gate is met**, which is the question this item existed to settle.
  None of the five gaps is structural — three are overload widenings on existing
  machinery, two are self-contained `comparator.py` additions — and the only
  genuinely blocked Java 8 items, `spliterator()` and `collect()`'s combiner,
  sit behind the real-parallelism decision **Later** says needs explicit buy-in.
  They cannot be what Java 9 waits on without waiting forever, so that entry is
  no longer sequencing-blocked; it competes with the five on merit.

  **Both of its premises expired, and the conclusion survived both.** The two
  "genuinely blocked" items are shipped — `spliterator()` and `collect()`'s
  combiner, by `fork-join-executor-and-spliterator` and `make-combiners-live`
  (2026-09-04) — so the real-parallelism decision this paragraph routes around
  no longer exists to route around; and there is nothing left for Java 9 to
  compete with on merit, the five having shipped by 2026-09-05. The gate is
  therefore met far more plainly than argued here: not "the blockers cannot
  count, so the gate opens", but "there is no gap". Java 9 stays in **Later**
  regardless, on a different reason than this one — it is undecided rather than
  blocked. Its row carries the current reasoning.

  Gap 5, `nulls_first`/`nulls_last`, is the one worth building on its own
  merits: `sorted()` over a stream containing `None` raises `TypeError` out of
  Python's comparison and there is no way to say where the `None`s go. The other
  four are parity for parity's sake. The five are filed as five rather than one
  batched entry — gaps 1-3 resemble each other only at the surface, and the
  batching call belongs to whoever picks them up.

  **How the batching call actually went (2026-09-05):** partly batched, and
  along a seam this paragraph did not predict. `f6406fe` took the two
  container-choosing collector overloads together (`to_map`'s fourth argument
  and `grouping_by`'s three-argument form — gaps 2 and 3, which share a shape
  after all, both being "let the caller supply the mapping"); `8cdcf31` took
  gap 5 alone, as predicted, on its own merits; `31860e6` closed the two
  `keyComparator` overloads that were struck-through *skips* here rather than
  gaps at all; and gap 1, `reduce`'s combiner, waited five days for a reason
  none of this anticipated — not its own difficulty but the executor
  underneath it, landing in `make-combiners-live` once fork/join could give a
  combiner something to combine.

  No behaviour changed: one docstring in `src/`, and `git diff -- tests/` empty
  at the end, which was the change's own tripwire.

- **`mark-order-blind-collectors`** (2026-08-31) — `counting()`,
  `summing_int()`/`summing_long()` and `summarizing_int()`/`summarizing_long()`
  declare `UNORDERED`, so they skip the racing delivery barrier. Nothing
  observable changes — each returns a value identical under either delivery
  order, which is what makes the declaration truthful — and the reason to make
  it is a cost the previous benchmark could not see. `race_through()`'s "nothing
  at all on IO-bound work" came from 40 elements at a **uniform** 10ms, where
  the reorder buffer never holds an element back; under tail latency (200
  elements, 90% at 2ms and 10% at 50ms) the barrier costs 1.12x, and with a
  periodic straggler 1.27x. The docstring now carries both shapes and says which
  one a uniform benchmark cannot measure.

  The floating-point family is excluded **permanently and in writing** rather
  than left undeclared: `summing_double()`, `averaging_*()` and
  `summarizing_double()` are order-*sensitive in fact*, float addition not being
  associative, and `summarizing_double()` sharpens it — one order-sensitive
  field makes the whole `NamedTuple` compare unequal however exact the fields
  beside it are. Item 4 had been reopened three times; silence is what allowed
  that, so the exclusions are now requirements.

  `_summing()` and `_summarizing()` take the mark as a per-caller parameter
  rather than deriving it from their `coerce` argument, which happens to agree
  today: sharing a body must not let `summing_double()` inherit
  `summing_int()`'s declaration.

  **Two claims made while proposing this were wrong and were corrected before
  implementing.** The change was pitched partly on `to_set()`'s barrier-skip
  being "guarded by nothing"; the test asserts the declaration and fails when it
  is removed, verified by hand. What was missing was the rule, not the guard —
  `racing-encounter-order` now states that a correctness-only assertion cannot
  discharge an order-blind scenario, that observation of arrival order is the
  method wherever the result permits it, and that timing must never be, because
  the property under test is which path ran and not how fast it ran. `to_map()`
  is left open, and item 5 says why it is not a parity gap.

- **`define-unordered-as-equality`** (2026-08-28) — `Characteristics.UNORDERED`
  now has one definition instead of two. It promises `==`-equality of the
  collected result and **nothing** about that result's iteration order, stated
  in the `Characteristics` docstring and in `collector-protocol` rather than
  inferred from the word "equal". The stricter reading that lived in two source
  comments — that nothing observable may differ — is withdrawn: a CPython `set`
  built from the same members in two orders is `==` while iterating
  differently, so the strict rule was both false in its premise and fatal to
  `to_set()`, its only declarer.

  Two consequences. `to_set()`'s justification is repaired — the requirement is
  unchanged, the reason for it is now set equality rather than the false
  structural claim. And `grouping_by()`/`partitioning_by()` **derive**
  `UNORDERED` from their downstream, the same one keyword `mapping()` and
  `collecting_and_then()` already used, on separate reasoning each:
  `dict.__eq__` is key-order-insensitive and the classifier is a function of
  the element, versus both partitions being seeded in the supplier. Nothing in
  `execution.py`, `_split_point()` or the barrier changed — only what two
  factories report to `collect()`.

  Silent break, recorded in README's migration log: on an ordered racing
  pipeline these two with an order-blind downstream no longer take the delivery
  barrier, so the returned mapping's key iteration order stops being
  deterministic. The value is unchanged under `==`; `.sequential()` or an
  order-observing downstream restores the order.

  This settles the **derivation** half of **Now** open question 4. The marking
  half — whether `counting()`, `summing_int/long()` and `summarizing_int/long()`
  should *declare* it — is still open and still owes a benchmark, and the float
  family plus `to_map(..., merge)` are recorded there as permanently unmarkable.

- **`order-min-max-tie-breaks`** (2026-08-28) — `.parallel().min()`/`.max()`
  now break ties in encounter order, resolving **Now** open question 3.
  `_min_max()` declares `observes_order=True` and takes the existing terminal
  clause in `_split_point()`; nothing in `execution.py` changed. Ties on a
  pipeline declared `unordered()` stay unspecified, matching Java, with
  `then_comparing()` as the lever for a caller who wants determinism without
  the barrier.

  Two facts found while writing it are why the "spec ties as unspecified"
  option was never really open. `comparator-contract` **already required**
  first-of-tied-in-encounter-order, so racing was violating an existing
  requirement rather than filling a gap; and `Stream.min()` and
  `collect(min_by(c))` **disagreed with each other**, the collectors having
  taken the barrier all along. The cost objection did not survive either:
  `sorted()` has always paid *more* for the same kind of determinism, splitting
  at its own index where `min`/`max` split at `len(chain)`.

  Two things landed alongside. `sorted()`'s **stability** is specified and
  tested for the first time — it held already, but nothing said so, and
  `racing-encounter-order` asserted the opposite in passing for the
  `unordered()` case, which is corrected. And `collector-min-max` now
  *requires* `min_by`/`max_by` not to declare `UNORDERED`, which takes them out
  of open question 4 permanently instead of by convention.

- **`ExceptionGroup` in `Stream.close()` is declined** (2026-08-28),
  resolving **Now** open question 2 after three batches of deferral — as a
  decision this time, not a fourth park. No code changed; the rationale is now
  written into the `stream-close-handling` spec, beside the rule it explains,
  which is what stops the question being re-asked.

  The objection recorded on 2026-08-18 was only ever "the CI matrix still
  targets Python 3.10", which needs a `sys.version_info >= (3, 11)` fork —
  an objection with an expiry date, and it has now expired: 3.10 left the
  matrix in `raise-python-floor-to-311` (2026-09-04). That is not why the
  answer is no. Java's `AbstractPipeline.close()`
  composes handlers through `Streams.composeWithExceptions()`: it runs every
  handler, calls `addSuppressed()` on the first exception for each later one,
  and rethrows *the first*. Java never throws a composite here. So
  first-exception-wins-with-the-rest-attached is the contract, and `add_note()`
  is its faithful Python spelling rather than a compromise forced by the
  version floor. An `ExceptionGroup` changes which type escapes `close()` —
  `except ValueError` around a `close()` silently stops matching — which is a
  divergence in *observable API behaviour*, the one category the guiding
  principle calls a defect.

  The case against, kept because it is not weak: PEP 654's own motivating
  example is multiple failures during cleanup, and a caller of an async-first
  library already handles `ExceptionGroup` from `asyncio.TaskGroup` and
  already writes `except*`. It loses on cost/benefit rather than on principle
  — two or more close handlers that both raise is the rare branch of a rare
  branch, programmatic catchability of the *second* failure buys nearly
  nothing over a note in the traceback, and the type change is paid by every
  caller. The `exceptiongroup` backport would remove the version fork at the
  price of this library's first runtime dependency, for its rarest code path;
  ruled out on sight.

  Nothing was touched but the spec: `stream.py`'s `close()`, both multi-raise
  tests, and the `noqa: PERF203` (whose stated reason — the run-every-handler
  contract — is unaffected either way) all stand unchanged.

- **`Comparator.thenComparing()`/`reversed()` chaining lands** (2026-08-28),
  resolving **Now** open question 1. The previously-private `_KeyComparator`
  becomes public `KeyComparator` holding an ordered tuple of
  `(key_extractor, descending)` segments instead of one extractor;
  `comparing(f)` still produces exactly one ascending segment, so every
  existing call reaches the code it reached before.
  `KeyComparator.then_comparing(other)` appends a segment or splices in
  another `KeyComparator`'s segments with their directions intact;
  `.reversed()` flips every current segment's direction — flipping each
  component of a lexicographic order equals negating the composite, which is
  what reproduces Java's before/after-chaining distinction with one
  implementation rather than two.

  `sort()`'s fast path generalizes from one key to k: columns are extracted
  concurrently across segments (not just within one, as before) via
  `asyncio.gather`, zipped into per-element tuples, and sorted in one Timsort
  pass across three lanes — all-ascending, all-descending via
  `sort(reverse=True)` (CPython's sort is stable in the strong sense under
  `reverse=True`, so this is exactly comparator negation, ties included, not
  a post-hoc buffer reversal), and mixed via a `_Descending` wrapper applied
  only to the columns that asked for one. Measured: a 2-segment chain over
  20,000 `(int, int)` tuples costs ~12ms all-ascending against ~40ms mixed
  (one descending segment) — the `_Descending.__lt__` indirection is the only
  place this capability leaves C, and it is paid only in the mixed lane. The
  single-ascending-segment case takes the exact pre-chaining code path — no
  tuple build, no outer gather — so `add-comparator-comparing`'s measured
  figures stand unchanged.

  README's `java.util.Comparator` table moves `thenComparing`/`reversed` from
  struck-through "decided against" to implemented, and records the
  `keyComparator` overloads as a deliberate skip instead — Python cannot
  disambiguate a one-argument key extractor from a two-argument comparator by
  signature, and accepting one would break the "every segment yields a key"
  invariant the fast path depends on being total. Not breaking: purely
  additive apart from the rename of a name with two in-repo references and no
  outside callers. See `openspec/changes/add-comparator-chaining`.

- **An ordered racing pipeline delivers in encounter order** (2026-08-28).
  **BREAKING**, and the break is the point: `.parallel().map(f).collect(to_list())`
  returned a scrambled list, which the guiding principle at the top of this file
  classifies as a defect — Java's ordered parallel streams preserve encounter
  order into `collect`, so "racing does not preserve encounter order" was the
  rule that had to go, not the accidental in-order delivery behind a barrier.
  The three things it settled, recorded because the reasoning took longer than
  the code:
  - **The barrier goes at `len(chain)`, not at index 0.** At index 0 the head is
    empty and the whole chain lands in the ordered tail — effectively
    sequential. At the end, every branch races the whole chain and only delivery
    is reordered, which is Java's shape and costs no per-element concurrency.
    `_split_point()` gained a third clause returning `len(chain)`, so one
    mechanism serves both callers and there is no second reorder implementation
    to keep in step.
  - **A terminal declares whether it observes encounter order**, as
    `observes_order`, a bool passed to `_evaluate()` and through
    `Executor.value()`/`elements()`. `count()`, `for_each()`, `find_any()`,
    `max`/`min` and the `*_match` family declare `False` and pay nothing;
    `collect(collector)` reads the collector's `Characteristics.UNORDERED`,
    which is the first and only reader of what `add-collector-characteristics`
    shipped, and the reason that change existed.
  - **`_resume_point()` was replaced, not tuned, and that is a concurrency
    *gain*.** It resumed racing only at an explicit `unordered()` because racing
    an order-blind suffix would scramble delivery; once delivery is reordered at
    the terminal that reason is gone. The barrier op runs one ordered pass and
    everything after it races. Measured: `.parallel().limit(8).map(50ms)` went
    **403.4 ms -> 101.7 ms**, the 4-branch floor exactly.

  **The cost, measured, because the proposal required it before landing.**
  Ordered delivery costs +33% per element (10.01 vs 7.51 us) on a 20,000-element
  `map(x + 1)` — but that is a chain too cheap to race in the first place. On
  40 elements at 10ms each, the shape racing exists for, ordered and
  `unordered()` are 105.5 ms and 106.9 ms: within noise, and both 4x ahead of
  sequential's 420 ms. So `unordered()` is measurably the faster path, as the
  spec promises, and the default regression is charged where it does not matter.
  Figures are in `race_through()`'s docstring.

  **One latent bug fixed on the way.** `is_ordered()` folded from `True`
  unconditionally, so the recursive re-entry over a chain *suffix* re-seeded the
  fold and read `.sorted(c).unordered().limit(3)`'s suffix as ordered, installing
  a barrier the caller had cleared two ops earlier. It now takes an `initial`
  seed, threaded through `race_through(ordered_in=...)`.

  Deliberately untouched, each with its own non-goal in the proposal:
  `find_first()` and `for_each_ordered()` (that is **Next** item 2), marking the
  collectors Java leaves unmarked, and exporting `_READ_AHEAD` (**Next** item 3,
  whose answer this flips to "export it"). Four delta specs —
  `racing-encounter-order` (2 added, 3 modified), `stream-execution-model`,
  `stream-iterator`, `collector-protocol` — plus a README migration entry, the
  CLAUDE.md ordering-barrier section, and a stale-`## Purpose` sweep over the
  three capabilities whose framing the change falsified. 727 passed,
  `--cov-fail-under=98` at 98.30%, `ruff`, `ruff format --check` and
  `ty check src` clean. One existing test changed meaning:
  `test_unordered_applies_only_to_ops_queued_after_it` asserted an in-order list
  from `.limit(5).unordered()`, which was the accidental behaviour; it now
  asserts the *selection* and lets delivery scramble, which is what the caller
  declared. See `openspec/changes/archive/2026-08-28-order-racing-delivery`.

- **`Stream._derive()` gains an optional `executor` argument, collapsing
  `sequential()`/`parallel()` to one line each** (2026-08-27). `_derive()`'s
  docstring claimed it derives "under the same executor", but its two mode-switch
  callers falsified that by hand — `derived = self._derive(); derived._executor =
  SEQUENTIAL; return derived` — the only place in `stream.py` where a method
  wrote a private attribute of an object it did not own. The fix is one
  parameter: `_derive(op=None, executor=None)`, with
  `new_stream._executor = executor or self._executor` replacing the
  unconditional assignment, so both derivation rules (chain and executor) live
  in the one method that already advertises itself as their home.
  `sequential()`/`parallel()` become `return self._derive(executor=SEQUENTIAL)`
  / `return self._derive(executor=RACING)`. Pure refactor: no behaviour change,
  no test edited, `--cov-fail-under=98` passes at 98.30% (691 passed), `ruff`,
  `ruff format --check`, and `ty check src` all clean. Fourth pass over this
  cluster; its proposal records why it is not a revert of
  `collapse-derive-wrappers`. Also retired that entry's `await`-in-`_derive()`
  tripwire (below) — `executor or self._executor` restores the assign-once
  property the tripwire existed to guard — and updated the CLAUDE.md paragraph
  that described the old two-statement mode-switch body. No delta specs:
  `.openspec.yaml` set `skip_specs: true`, no capability names `_derive()`. See
  `openspec/changes/archive/2026-08-27-unify-derive-signature`.

- **`Collector` gains a `characteristics` frozenset and `Characteristics.UNORDERED`**
  (2026-08-27). Matches OpenJDK's assignments exactly: `to_set()` declares it,
  `mapping()`/`collecting_and_then()` derive it from their downstream, and
  every other factory — `counting()`, `summing_*`, `averaging_*`,
  `summarizing_*`, `to_map()`, `grouping_by()`, `partitioning_by()`,
  `min_by`/`max_by` — stays unmarked, matching Java's own choice not this
  library's judgment. `grouping_by()`/`partitioning_by()` take a downstream but
  deliberately do not derive from it: the downstream's result is a map value,
  not the collector's own result. The fifth constructor parameter defaults to
  a shared empty `frozenset`, so every existing `Collector(...)` call, in this
  library and in user code, is unaffected — additive, not breaking. **Ships
  inert**: nothing reads the characteristic yet, and that is stated in the
  code, the tests and the README rather than left implicit, so it does not
  read as dead code. Was **Now**'s item 1 and **Next**'s item 4 before that.
  `openspec validate --strict`, `ruff`, `ty check`, and `pytest
  --cov-fail-under=98` (691 passed, 98.30%) all pass. See
  `openspec/changes/archive/2026-08-27-add-collector-characteristics`.

- **`comparing(key_extractor)` ported from Java's `Comparator.comparing`**
  (2026-08-27). `sorted()`, `min()`, `max()`, `min_by()` and `max_by()`
  previously accepted only a 3-way `Comparator`, the most expensive way Python
  can express an ordering — every comparison forces a `cmp_to_key` call, and an
  async comparator forces the hand-written `merge_sort` because `list.sort`'s C
  loop has no point to return control to the event loop. Measured sorting dicts
  by one field: **6.8-8.8x** for a sync key extractor over a sync comparator,
  **4.8-5.4x** for async, where it also collapses the interleaved-await count
  from O(n log n) to O(n). See
  `openspec/changes/archive/2026-08-27-add-comparator-comparing`.

  **`comparing()` returns an object, not a closure.** A literal port of Java's
  `(a, b) -> k(a).compareTo(k(b))` would be a regression: the key would be
  called twice per comparison, O(n log n) times, so an async key would cost
  `2n log n` awaits. The returned `_KeyComparator` instead exposes the key
  extractor as a plain attribute so `sort()` can recognize it and take a
  decorate-sort-undecorate fast path, while still implementing `__call__` as an
  ordinary `Comparator` for `min()`/`max()`/`min_by()`/`max_by()`, none of which
  know about the fast path.

  **The fast path sorts on the key alone, never on `(key, element)`.** An
  explicit key selector over the paired list, not a bare tuple sort — Timsort's
  stability then gives encounter order for equal keys for free with no
  tie-break index, and the *elements* are never compared, so one that doesn't
  support `<` still sorts as long as its key does. No sign or `bool` validation
  reaches this path either: a key extractor returns a key, not a comparison
  result, so `check_comparator_result_type`/`_checked`/the trial probe are all
  skipped, and an incomparable-key `TypeError` propagates from `list.sort`
  unwrapped.

  **Async key extraction gathers concurrently, reversing a task written before
  benchmarking.** The design deferred "sequential loop or `asyncio.gather`?" as
  an open question, and the sequential loop shipped first, per its own task,
  with no trial-comparison probe — reasoned as unnecessary since a loop always
  has an `await` point available. Benchmarked before the gate run with an
  I/O-bound extractor (`sleep(0.001)` per key, the shape a real async extractor
  actually has): 1,000 elements cost **1325ms sequential vs. 9ms gathered**. A
  sequential loop was paying the full `n * latency` regardless of the extractor
  being async — exactly the concurrency `comparing()`'s async case exists to
  buy, and the loop was throwing it away. Switched to `asyncio.gather()`, which
  *reinstates* a trial call on the first element (the same shape as `sort()`'s
  own trial comparison) so the one-time `isawaitable` safety net's coroutine
  joins the gather instead of being discarded — invocation count stays exactly
  n either way. The reversal is recorded in design.md rather than the
  now-stale task line being silently correct in hindsight, on this project's
  rule that a superseded decision is annotated, not erased.
  **Accepted trade-off:** `gather`'s failure semantics apply — first exception
  wins, not left-to-right — and every element's key coroutine is in flight
  concurrently rather than one at a time. Both follow from the same reason the
  capability exists: an async key extractor's value is entirely in not
  serializing its awaits.

  **New capability spec `comparator-comparing`**, five requirements: builds a
  `Comparator` from a key extractor and is accepted anywhere one is; the
  extractor may be sync or async; sorting invokes it exactly once per element,
  not once per comparison (the property the capability exists for); ordering by
  key is stable; keys must be mutually comparable, with `bool` keys explicitly
  a legitimate ordering rather than an error. `comparator-contract`'s
  bool-rejection rule is unaffected — a key extractor returns a key, never a
  comparison sign, so there is no `bool <: int` hazard on this path to guard.
  27 new tests in `tests/test_comparing.py`, including a drift test asserting
  the fast path and the `__call__` path agree on the same comparator (ties,
  `bool` keys, a property-based comparator-vs-`cmp_to_key` check), an exact
  invocation-count test, and the misclassified-sync safety-net path (a `def
  __call__` that manually returns a coroutine).

  **README gained a third parity table** — `Comparator`, alongside `Stream` and
  `Collectors` — recording `comparing()` as implemented and `thenComparing`,
  `reversed`, `naturalOrder`, `reverseOrder` as deliberately skipped with their
  reasons, in the same struck-through style the `Stream` table already uses so
  "not yet" reads differently from "decided against". `thenComparing()`'s
  workaround (`comparing(lambda x: (a(x), b(x)))`) is documented in
  `comparing()`'s own docstring, since it is exactly what a future
  `thenComparing()` would compile to.

  **Not breaking.** Every existing comparator path, `merge_sort` included, is
  untouched; `comparing()` is a new way to build a `Comparator`, not a change
  to what one means. 673 tests green, `ruff`, `ruff format --check`,
  `ty check src`, and `--cov-fail-under=98` at 98.30% all pass.

  **Landing this is the precondition for two items `add-comparator-comparing`'s
  own proposal named out of scope**: replacing `merge_sort` with a smaller
  algorithm, and retiring the async comparator path altogether. Both were
  deferred specifically because they become easier to judge once `comparing()`
  exists and it is visible how much traffic still reaches the comparator path
  rather than the key path — that visibility didn't exist until now.

- **Collapse `Stream._compose()` into `iterator()`** (2026-08-27). `_compose()`
  had shrunk, since the executor-value redesign, to a one-line forward to
  `self._executor.elements(...)` — the only thing separating it from the
  public `iterator()` was the `_check_not_consumed()` call `iterator()` makes
  and `_compose()` skipped. That gap was reachable from user code in exactly
  two of its four call sites: `Stream.concat()` and a `flat_map()` mapper's
  return value could both slip an already-extended stream past the
  pipeline-immutability contract. Deleted `_compose()` and routed all four
  callers — `_concat()`, `_FlatMapSink.accept()`, `collect()`'s
  `StreamingCollector` branch, and `iterator()` itself — through `iterator()`.
  See `openspec/changes/archive/2026-08-27-collapse-compose-into-iterator`.

  **BREAKING (behavioural, previously unspecified):** `Stream.concat()` and a
  `flat_map()` mapper now raise `IllegalStateException` on an already-extended
  argument. Neither was ever documented as accepting one, so no README
  migration-log entry — the two newly-raising cases were unsupported
  before this, just silently so. A stream that was merely *terminally
  consumed*, never extended, is unaffected in both positions.

  **`_concat()` moved the check out of its own body, not into it.** It is an
  `async def` generator, so a `_check_not_consumed()` call inside it would not
  run until first pull — a materially weaker guarantee than "raises when you
  call `concat()`". `Stream.concat()` now calls `a.iterator()` / `b.iterator()`
  itself before constructing `_concat(a.iterator(), b.iterator())`, which also
  dropped `_concat()`'s only dependency on `Stream`: it takes two
  `AsyncGenerator`s now, nothing else.

  **Four specs touched, no guarantee changed except the one stated above.**
  `pipeline-immutability` gained the argument-position scenarios;
  `pipeline-composition`, `stream-iterator`, and `mutable-reduction-collect`
  had prose restated from `_compose()` naming to the executor vocabulary they
  already used elsewhere — a legibility fix, not a behaviour change.
  `pipeline-composition`'s `## Purpose` named both `_compose()` and the
  already-stale `_parallel()` (deleted by the executor-value redesign); hand-
  edited at archive time, since a delta can't carry `## Purpose` for an
  existing capability.

- **Ordered `sorted()`/`limit()`/`skip()`/`distinct()` under `RACING`**
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

- **Collapsed the derive wrappers into one copier** (2026-08-26). `_extend(op)`
  and `_derive_executor(executor)` were one-expression wrappers over
  `_derive(chain, executor)`, each passing one axis through unchanged while the
  call site wrote the other as noise. There is now one
  `_derive(self, op: Op | None = None) -> Stream[Any]`: the chain-extension rule
  lives in its body, and `sequential()`/`parallel()` derive with no op and
  assign `_executor` themselves. See
  `openspec/changes/archive/2026-08-26-collapse-derive-wrappers`.

  **This is the third pass over the same cluster, and what matters is why it is
  not a revert of the first.** The 2026-08-24 merge landed the same one-copier
  shape and was undone in two steps — `_extend` on 2026-08-25, then
  `_derive_executor()` re-added on 2026-08-26 — because it paid two costs, and
  both are avoidable independently of the layer count:

  - *The copier took a pre-built chain*, so each of the nine op methods spelled
    out `[*self._chain, op], self._executor` and the `Op` the method is *about*
    became the least visible part of the line. Taking the `Op` instead puts the
    rule in the callee: `return self._derive(_MapOp(mapper))`, which is
    `_extend`'s ergonomics exactly. That property is what had to survive, and it
    did.
  - *The docstring was copied verbatim onto both public methods.* It now sits on
    `sequential()` alone, at full length, with `parallel()` pointing at it —
    because the new body is a working template for the move
    `pipeline-immutability` forbids: delete one line and
    `derived._executor = RACING` becomes `self._executor = RACING; return self`.
    The warning moved to where the temptation now is rather than staying where
    it happened to be.

  `op is not None`, not `if op`: every `Op` is truthy today, but `_UnorderedOp`
  carries no state, and an `Op` that later grew `__bool__`/`__len__` would be
  silently dropped from the chain by a truthiness test. **Accepted knowingly:**
  `_executor` is no longer assigned exactly once per instance — the copier sets
  it and the mode method overwrites it. Unobservable today (no `await` between
  the two statements, the instance has not escaped), and recorded so that adding
  an `await` to `_derive()` is recognised as breaking it. **Retired by
  `unify-derive-signature` (2026-08-27):** `_derive()` grew an `executor`
  parameter and assigns `new_stream._executor = executor or self._executor`
  once, so there is no longer a second statement for an `await` to land
  between.

  **`_derive()` stays a method on `Stream`**, explicitly rather than by default.
  Moving it beside `execution.py`'s `_wrap_sink`/`_copy_into`/`stream_through`
  fails that family's own membership rule — none of them needs a stream
  instance, and `_derive()` *is* the thing. The `self._consumed = True` it
  performs is the `pipeline-immutability` invariant, and an invariant enforced
  from outside the class is one every future call site can route around. Checked
  against the roadmap rather than assumed: neither a third `Executor` nor
  `spliterator()` constructs a `Stream`, so neither creates the payoff a
  module-level version would need.

  **583 tests green with no test file edited** — the tripwire, since
  `pipeline-immutability`, `pipeline-composition` and `stream-execution-model`
  already pin every contract touched, including that a queued chain survives a
  mode switch. `ruff`, `ruff format --check`, `ty check src`,
  `--cov-fail-under=98` (98.06%) and `openspec validate --strict` all pass.
  `skip_specs: true`: no observable behaviour changed. Off the per-element path
  (chain-building and mode-switch code, run once per composition), so no
  benchmark gate applied. The dead `cast()` went in a separate first commit —
  `_derive()` returns `Stream[Any]` and `Any` is assignable to `Stream[T]`, the
  same finding the 2026-08-25 batch made for the eight intermediate ops, which
  never reached these two methods because they called `_derive()` directly then.

  **The prose sweep found more than the tasks named, and that is the reusable
  lesson.** Five stale references were annotated, not three: the tasks cited
  `roadmap.md:1195` and `727-745`, both of which had drifted, and the sharpest
  one they missed was the 2026-08-26 entry claiming "`_derive_executor()` now
  exists and owns the shared explanation". History entries are annotated as
  superseded, never rewritten to pretend the prior shape never existed. This is
  not tidiness — `_derive_executor()` was resurrected in the first place
  *because* `CLAUDE.md` described a method that did not exist, and leaving the
  Done entries stale would arm the same mechanism again. Cite the sentence in a
  documentation task, not the line number.

- **`is_ordered()` left the public API** (2026-08-26). Renamed to
  `_is_ordered()`. Java has no such accessor to be at parity with: `BaseStream`
  exposes exactly one piece of pipeline introspection, `isParallel()`, while the
  ordering characteristic lives in the package-private `StreamOpFlag.ORDERED`
  and is never readable by a caller. The question that surfaced it was "where is
  `Stream.ordered()`?" — and the answer is that Java has no `ordered()` either,
  because ordering is a spliterator characteristic contributed by the source,
  only ever cleared by `unordered()` or re-imposed by `sorted()`. Both are now
  struck-through rows in README's parity table. See
  `openspec/changes/archive/2026-08-26-make-is-ordered-internal`.

  **Renamed, not deleted, and not inlined** — the second half was the live
  question, since the fold turned out to have exactly one caller
  (`for_each_ordered()`; `find_first()` stopped consulting it in
  `make-ordering-a-chain-characteristic`, and `CLAUDE.md` had been stale about
  that ever since, now fixed). Inlining five lines into a single caller is the
  ordinary call and was still rejected: three mode-switch scenarios have no
  behavioural observable and pin their rule through the accessor, so inlining
  collapses into dropping them — and it is the rule whose earlier violation
  produced a wrong answer. The docstring also records *why* the fold is not
  cached onto the instance, which is reasoning nobody finds inside a method
  about consuming elements.

  **The rewrite of the tests is what this change actually cost.** Replacing
  accessor assertions with behavioural ones silently weakened them, and a
  mutation check caught it: with `_SortedOp` altered to preserve rather than set
  the characteristic, all four rewritten `sorted()`-restores tests still passed.
  They were reverted to `_is_ordered()` assertions, and the reason — that (a) in
  **Now** makes a sort under `RACING` indistinguishable from an unordered one —
  is recorded in the spec, in `tests/test_unordered.py`, and as test debt on (a)
  itself, along with a pre-existing weak test the same sweep found in
  `tests/test_for_each_ordered.py`. **The lesson generalises: "assert on
  behaviour, not on internals" is right until the behaviour is broken, and a
  test rewrite is not verified by the suite going green afterwards.**

- **Ordering became a chain characteristic instead of an instance flag**
  (2026-08-26). `unordered()` set `self._ordered = False`, so it applied to the
  whole pipeline no matter where it was written — `parallel()`'s rule, copied
  onto the one method Java deliberately gives the opposite rule. Java's
  `parallel()` sets a field on the *source stage* precisely so as to be
  position-independent; its `unordered()` is a `StatelessOp` contributing
  `NOT_ORDERED`, folded downstream only by `combineOpFlags()`, and its
  `sorted()` contributes `IS_ORDERED` back. See
  `openspec/changes/make-ordering-a-chain-characteristic`.

  **The drift produced a wrong answer, not just an inelegance.** Because a
  field cannot be re-set by a later stage, `sorted()` could not restore
  ordering, and the flag's only consumer — `find_first()`, which degraded to
  `find_any()` when unordered — then returned a branch-local minimum of a
  sorted pipeline. Measured over an async source of `range(200, 0, -1)` under
  `.parallel()`, ten runs each:

  ```
  .parallel().sorted(asc).find_first()              ->  1 1 1 1 1 1   (correct)
  .parallel().unordered().sorted(asc).find_first()  ->  2 4 4 2 3 4   before
  .parallel().sorted(asc).unordered().find_first()  ->  2 4 4 3       before (identical: global)
  .parallel().unordered().sorted(asc).find_first()  ->  1 1 1 1 1 1   after
  ```

  Java returns the minimum in all of them. The last line is pinned by
  `test_find_first_after_unordered_and_sorted_returns_the_smallest`, run ten
  times because the wrong answer was nondeterministic.

  **`Ordering` (`sink.py`) is a three-member enum — `PRESERVE`/`CLEAR`/`SET` —
  on `Op` as a `ClassVar`, defaulting to `PRESERVE`.** Only `_SortedOp` (`SET`)
  and the new `_UnorderedOp` (`CLEAR`) state it; the other seven take the
  default, which is also what Java says about them. A `ClassVar` because
  ordering is a property of the *operation*, not of the arguments: every sort
  sets it, whatever comparator it was given. **Java's semantics were ported,
  its encoding was not** — `StreamOpFlag` packs two bits per flag in an int
  because it carries five characteristics through a fold that runs on every
  stage, and we carry one.

  **`_UnorderedOp` is the one op with no sink.** `link()` returns the
  downstream untouched, exactly as Java's `opWrapSink(flags, sink) { return
  sink; }` does, so it cannot observe, transform, reorder, drop or duplicate
  anything and never enters the sink chain at all. Measured: `count()` over
  20k elements, 9.32 ms without it and 9.29 ms with it queued (**-0.3%**, i.e.
  noise). It exists only to occupy a position and declare a characteristic
  there — which is the whole of what makes ordering positional.

  **`is_ordered()` folds the chain and stores nothing.** 311 ns over a
  five-op chain, called at most once per terminal. **The O(1) alternative was
  measured and rejected, and should not be re-proposed**: updating a cached
  `_ordered` incrementally in `_extend()` (`_derive(op)` since 2026-08-26) from
  the op being appended is exactly
  equivalent (the chain only ever grows by append) and saves those 311 ns, but
  reinstates a denormalised copy of a chain property that every future derive
  path must remember to maintain — which is the precise failure mode this
  change exists to remove. `_ordered` is gone from `__init__` and from
  `_derive()`'s copy list.

  **Two breaking changes, both in README's migration log.** `unordered()`
  returns a new instance and consumes the receiver, joining the enumerated
  intermediate ops in `pipeline-immutability` rather than sitting as a
  footnote against it — the exemption existed only because it had no chain
  element to append. And `find_first()` dropped its `is_ordered()`
  short-circuit and always drives `SEQUENTIAL`: **Java does not relax
  `findFirst()` on an unordered stream either.** `FindOp.mustFindFirst` is
  fixed when the op is constructed and `FindTask` does its leftmost scan
  whenever it is set, never consulting upstream `ORDERED` — the javadoc
  permits returning any element there, the implementation declines to.
  `find_any()` is where a caller who wants the race goes.

  **`for_each_ordered()` gained the relaxation `find_first()` lost**, and is
  now the flag's consumer: on an unordered pipeline it runs under the stream's
  own executor instead of forcing `SEQUENTIAL`, matching
  `ForEachOps.OfRef.evaluateParallel()`'s choice between `ForEachOrderedTask`
  and `ForEachTask`. This closes the note left in this roadmap's
  `add-stream-foreach-ordered` entry, which said the flag was not consumed
  there because `unordered()` "doesn't currently model" streams with no
  defined encounter order. It does now.

  582 tests green, up from 567 — three of which this change turned around
  rather than added to: `test_unordered_returns_self_for_chaining`,
  `test_unordered_parallel_find_first_races` and
  `test_find_first_on_unordered_parallel_stream_races` all asserted the
  behaviour being removed. Coverage 98.06%, `ruff`, `ruff format --check` and
  `ty check src` clean. Four spec deltas — `stream-ordering`
  (+3 requirements, ~1, -2), `stream-find-first` (+1, -1),
  `stream-foreach-ordered` (+1, ~1), `pipeline-immutability` (~2). Left open
  deliberately, and **written up in Now**: `limit`/`skip`/`distinct` still
  ignore the characteristic under `RACING`, and `sorted()` under `RACING` does
  not sort at all. This change's own design doc framed the first three as a
  missed optimisation — Java exploiting unorderedness to run cheaper — and that
  was backwards. All three already behave as if unordered unconditionally, so
  what is missing is the *ordered* path, and they are wrong answers on an
  ordered stream rather than slow ones. Confirmed by measurement after the
  change landed; the figures are in **Now**. What this change contributes is
  that the branch is now expressible: `is_ordered()` gives a reliable
  positional answer where the old instance flag did not.

- **The lint gate extended to `tests/`** (2026-08-26). Both **Next** items at
  once, because they were one edit: `PT011` could not be fixed without enabling
  `PT`, which was the `tests/` question.
  `openspec/changes/extend-lint-gate-to-tests`.

  **Both of this roadmap's figures for the item were wrong, and measuring
  before planning changed the change.** The recorded **61** was a trial set
  that omitted `PLR`, `PLW`, `RET`, `PIE` and `FURB`; the real total under the
  selection actually in `pyproject.toml`, plus `PT`, was **283**. Of those,
  **218 were `PLR2004`** alone — magic-value-comparison, firing on
  `lambda x: x > 5` and `assert largest == 7`, which in a test is the data and
  the expected value. Exempted for `tests/` and only there, by **rule and not
  by family**, so the rest of `PLR` still applies to tests and `PLR2004` still
  applies to `src/`. That distinction earned a spec requirement of its own: the
  previous change's entry switched off eleven whole families, and the
  difference between the two is the whole quality of the gate. The remaining
  **65** findings (~54 sites, since `B011` and `PT015` flag the same eleven)
  were all fixed; `ruff check .` is now clean over the whole tree.

  **The roadmap also had `PT011` backwards, and the correction is the more
  useful record.** It described three `pytest.raises(Exception)` sites to be
  narrowed to `StreamException` now that story 1 had shipped it. They are
  `pytest.raises(ValueError)` in `test_exception.py`, and the
  `ValueError("boom")` is raised by a **user callback** the test installs, to
  prove a user exception propagates out through `map()`/`filter()` sequentially
  and in parallel. Naming a library base would have asserted the opposite of
  the test's purpose. `match="boom"` was the fix that fits.

  **The `assert False` claim needed correcting too, mid-apply.** The change was
  planned on the premise that `python -O` strips those eleven guards outright,
  making them silently pass — a live correctness bug. That is false for this
  suite: pytest rewrites assertions inside test modules at import time, so
  `assert False` fires under `-O` as it should. What the rewrite actually buys
  was then measured against a baseline worktree at HEAD, under
  `-O --assert=plain`: **before, 37 passed; after, 10 failed** reading
  `Failed: stream should be exhausted`. Those 37 were vacuous — these tests
  advance the stream *inside* their assertions, so with assertions stripped the
  stream is never consumed, the guard's `try` succeeds, and the old
  `assert False` in the `else:` was stripped as well. The rewrite does not make
  that configuration work; it makes it say so instead of reporting green. Plus
  the plain win: `pytest.fail(msg)` names what did not happen where
  `assert False` said nothing.

  The rest: 22 `SIM300` yoda conditions, 3 `PT006`, 3 `PT018` composite
  assertions split so a failure names which half broke, 4 `PLW0108`, 2 `C417`,
  2 `RET505`, 1 each of `SIM401`, `PLR1711`, `PLW1510` (explicit `check=False`
  — callers assert on `returncode`, so only the implicitness was the finding).
  One inline suppression, `PT012` on `test_base_is_not_a_value_error`, where
  the `try`/`except ValueError` inside `pytest.raises(StreamException)` is the
  mechanism the test exists to demonstrate. 25 of the fixes were taken with
  `ruff check --fix`; `--unsafe-fixes` was deliberately not used, since its
  extra fixes reach into assertions.

  **The tripwire was inverted from the previous change and held.** That one
  required no test file be touched; this one is 18 test files and 69 changed
  lines, so the rule was the count — **567 passed**, unchanged — plus a read of
  every hunk confirming each is the same assertion restated or a strictly
  stronger one. No `src/` file was touched, coverage held at 98.04%, `ty` clean.

- **Built-ins, stdlib and the lint gate** (2026-08-26). Story 2 of the second
  2026-08-25 batch, and the one that waited on story 1. Six findings, one
  change: `openspec/changes/builtins-stdlib-and-lint-gate`.

  **The tripwire held.** 567 tests pass with **no test file edited**, coverage
  98.04% against the 98% gate, `ty check src` clean, and the diff touches
  exactly eight files — the seven modules named in the story plus
  `pyproject.toml`.

  **(a) `anext()` at all three sites**, `_guarded`'s and both of
  `race_through`'s. **The roadmap was wrong that this story faces no
  per-element code**: all three of these run once per element, not once per
  composition, and the "do not spend a harness run on it" note applied to
  everything in the story except exactly this part. Measured rather than
  asserted, 300k elements, five reps, both orderings: `anext(it)` **69ms**
  best / 70ms median against `it.__anext__()` **79ms** best / 81ms median —
  about **13% faster**, ~35ns per element, the builtin's type-level lookup
  beating the instance attribute lookup. So the per-element hunk is a small
  improvement. The `aiter()` comment at `:151` was left alone (it explains
  arity, not the builtin); the adjacent `:153` comment was refreshed to name
  the call the next line makes.

  **(b) `_finish_groups` and `partitioning_by._supply`.** The invariant left
  the loop rather than the comprehension merely wrapping the branch: no
  finisher now returns `dict(groups)` outright, and the finishing arm is one
  async dict comprehension. `_supply` builds its two-key dict directly.

  **(c)** `[*self._chain, op]` in `_extend` (that line lives in `_derive()`
  since 2026-08-26). **(e)** `dist_name` joins the
  `finally: del`; `snakestream.dist_name` is gone (verified importable before,
  absent after) and `__version__` still resolves.

  **(d) `Mapper` lost its `None` arm entirely** rather than taking `RUF036`'s
  reordering. The user's call, put before the specs were written. The union
  widened every `.map()` result to optional for nothing — a mapper returning
  `None` is already `R = None` — and `ty` confirms the fix: `.map(to_str)` now
  reveals `Stream[str]` where it read `Stream[str | None]`, and a `str | None`
  mapper still binds `R` to `str | None`. No internal site was leaning on the
  optional. `Consumer` and `BiConsumer` took the plain reorder, `None` to the
  tail. Recorded as a delta on the `generic-stream-typing` spec, since a typed
  `map()` result is externally visible.

  **(f) The selection widened to
  `E,F,W,C90,UP,ASYNC,B,SIM,RUF,PERF,C4,RET,PIE,FURB,PLR,PLW`** — exactly the
  trialled set, no family added unmeasured. **The trial was over `src/` and the
  gate is not**: `ruff check .` immediately turned up 262 findings in `tests/`,
  which the story excluded. Resolved with a `per-file-ignores` entry dropping
  the new families for `tests/**` while `E,F,W,C90,UP` still apply everywhere,
  so the scope the story decided is the scope the config enforces. `src/` is
  clean. `B008` took the `_TO_LIST` module-level default over a `noqa`, so the
  statelessness argument sits where the default is written; `RUF023` sorted
  `Collector.__slots__`; and both false positives carry a rule-scoped `noqa`
  with its reason inline — `B004` on `callable_dispatch.py`'s class-level
  `__call__` lookup, `PERF203` on the close-handler loop. Neither is a
  file-level ignore. **`ASYNC` still finds nothing**, which was the argument
  for it.

- **`collectors.py` split out of `collector.py`, and four legibility gaps**
  (2026-08-26). Story 1 of the second 2026-08-25 batch, and the one the other
  story waited on.

  **The roadmap row was wrong about the blast radius, and that was the first
  finding.** It called story 1 "private-surface only apart from one new public
  exception base." `snakestream.collector` is public: README's quickstart
  imports `to_generator` from it and 46 files under `tests/` imported factories
  from it. Moving the factories is a **breaking import-path change**, and it
  was surfaced and decided before any artifact was written rather than
  discovered mid-apply. The user chose the Java-faithful break over a
  re-export shim, an inverted split, or moving `to_generator` too.

  **The split is `Collector` / `Collectors`, and it cost no invented name.**
  `collector.py` keeps the protocol — `Collector`, `_CollectorSink`,
  `StreamingCollector`, `_stream`, `to_generator` — at 114 lines.
  `collectors.py` takes the ~22 factories plus `SummaryStatistics` and the
  private helpers and container dataclasses only they use, at 545. The import
  edge runs one way and is now visible as an import rather than implicit in
  file ordering, the same shape the `sort.py`/`comparator.py` split settled
  on. It also disentangled the `collector.py` -> `execution.py` import of
  `_maybe_aclosing`, which existed solely for `_stream` and travelled with the
  protocol half; two imports went dead in the process (`_maybe_await` in
  `collector.py`, `type.A` in `collectors.py`) and were removed.

  **`to_generator` stayed put, and that was the deliberate half of the
  decision.** It is a `StreamingCollector` instance, not a factory, so it
  belongs beside the type it instantiates — and the `collector-protocol` spec
  already singled it out as "the one non-`Collector` collector". Moving it to
  sit with the factories would have re-created, inside `collectors.py`,
  exactly the two-things-in-one-module problem the split was fixing. It also
  means README's quickstart import is unchanged.

  **The move is provably verbatim.** Diffing the original
  `collector.py:125-633` against `collectors.py` from `to_list` onward:
  identical, byte for byte. That is what settles the benchmark question the
  row raised — no factory body was reformatted or reordered, so no per-element
  path could have been touched, and no harness run was needed. The remaining
  `src/` diff is 42 insertions across four files, none inside an `accept()`
  body or an accumulator inner function.

  **`StreamException`, named by the user over `SnakestreamException`.** Java
  has no common base for its stream exceptions, so the Java-parity rule did
  not decide this one. Inserted above `StreamBuildException` and
  `IllegalStateException`, source-compatible by construction. The temptation
  refused was giving it a second base such as `ValueError` to soften the
  previous batch's `to_map` break — refused for the reason that batch already
  recorded: the same hierarchy covers stream-reuse errors, and a stream-reuse
  error is not a `ValueError`. New capability `exception-hierarchy`, five
  scenarios, five tests.

  **`CLAUDE.md` was already describing a method that did not exist.** Its
  "Sequential vs. parallel execution" section states that `.parallel()` /
  `.sequential()` "go through `_derive_executor()`" — but the code called
  `_derive(self._chain, EXEC)` directly and the two public methods carried the
  same twelve-line docstring verbatim, which was the row's finding (b). The
  fix made the code match the documentation rather than the other way round:
  `_derive_executor()` now exists and owns the shared explanation, and both
  public methods are one-liners. **Superseded 2026-08-26 by
  `collapse-derive-wrappers`**, which read this entry the other way round: the
  duplicated docstring was the real finding, and a wrapper method is not the
  only way to hold it. `_derive_executor()` is gone again; `sequential()` owns
  the explanation and `parallel()` points at it, so there is still exactly one
  copy of it — and `CLAUDE.md` was corrected in the same change, which is the
  half of this entry that still stands.

  **The `TerminalSink` contract was documented, not changed.** The row was
  explicit that the three dependents must not gain defensive `await`s, and
  they did not: `_CollectorSink._create_container()` is still `def`, and
  `grouping_by`'s and `partitioning_by`'s `_finish` still return the
  un-awaited coroutine of `_finish_groups()`. Verified by grep after the edit,
  not assumed.

  **The tripwire had to be restated before it could hold.** "The suite passes
  with no test file edited" is unachievable once 46 import lines move, so it
  became mechanical: `git diff -U0 -- tests/` must show import lines only. It
  did, across all 45 files that changed — no assertion touched.

  **Coverage identity held exactly, which is the check the previous batch
  taught.** Missed statements 2 -> 2, branches 288 -> 288, partial branches
  26 -> 26; the uncovered set is the same two lines in `_summarizing`, now at
  `collectors.py:192-193`. Total went 98.05% -> 98.05%. Compare the counts,
  not the percentage.

  **One thing the sync surfaced that the plan did not.** `collector-protocol`'s
  main-spec `## Purpose` read "every `collector.py` factory returns", which the
  requirement directly below it now contradicted. Corrected to `collectors.py`
  — a module name this change itself renamed, not a Purpose rewrite — and
  flagged rather than done silently.

  567 tests green. `ruff`, `ruff format --check`, `ty check src` (output
  identical to baseline), `--cov-fail-under=98` at 98.05%, and
  `openspec validate --specs` at 37/37 all pass. Spec deltas on
  `collector-protocol` (2 MODIFIED) and `exception-hierarchy` (new), plus two
  README migration entries. See
  `openspec/changes/archive/2026-08-26-split-collector-protocol-and-factories`.

- **Collector containers, and the duplicate-key exception** (2026-08-25).
  Story 6 of the 2026-08-25 batch — independent of the other five, and the one
  that closed the batch. Three unrelated defects that shared a neighbourhood.

  **(a) Nine hand-written containers became `@dataclass(slots=True)`.**
  `_SumBox`, `_AvgBox`, `_SummaryBox`, `_ExtremumBox`, `_ReduceBox`,
  `_ToMapBox`, `_GroupBox`, `_MappingBox`, `_CollectAndThenBox` each declared a
  `__slots__` tuple and then wrote the same field list again in an `__init__`.
  `slots=True` emits the same descriptors, so this is not the rejected
  `CallSite` proposal wearing a new hat: those containers are built once per
  collection by a collector's `_supply()`, never per element, and attribute
  access inside `_accumulate` is unchanged. **Verified rather than asserted** —
  a before/after harness compared slot names, constructed values and the
  absence of `__dict__` across all nine and found them identical.

  **The "~90 lines of boilerplate" the roadmap row claimed is not the number.**
  The real saving is **-34 lines** (`collector.py` -25, `sink.py` -9). The ~90
  counted the gross volume of `__slots__` tuples plus `__init__` bodies, but
  the dataclass field declarations that replace them occupy most of that space
  — a field is still a line. Only `_ToMapBox` is a large win (-10), because its
  seven-field `__slots__` tuple was formatted across nine lines. The other
  eight are -2 each. Legibility, not line count, is what this part bought:
  the field list is now stated once.

  **One field order had to change.** `_SummaryBox` took `seed` positionally but
  declared `count` first, and a required dataclass field cannot follow
  defaulted ones, so `total` moved to the front. Its single construction site
  is `_SummaryBox(seed)`, so it still binds correctly — but it is a real
  reordering, not a transcription, and it is the one place where the "change
  nothing but the boilerplate" goal bent.

  **(b) `Counter` is deleted, not renamed.** It shadowed `collections.Counter`
  and added exactly one thing to `Box`: a default of `0`. Deleting it was the
  user's call over a rename. The two `ops.py` `make_shared_state()` bodies
  return `Box(0)`, and `counting()` — which had been passing the class object
  itself as the supplier, `Collector(Counter, ...)`, relying on that default —
  became `Collector(lambda: Box(0), ...)`. `partial(Box, 0)` was rejected as a
  `functools` import for one call site.

  **(c) `to_map` raises `IllegalStateException`, and it stays a `ValueError`
  break.** Java's `Collectors.toMap` throws `IllegalStateException` on a
  duplicate key, and this project already defines that class and already raises
  it for pipeline reuse. The tempting softener — deriving `IllegalStateException`
  from `ValueError` so existing `except ValueError` sites keep working — was
  **rejected, and the reason is the other raise site**: the same class is what a
  reused-stream error raises, and a stream-reuse error is not a `ValueError`
  under any reading. Softening the break here would have mis-typed it there.
  Loud for `except ValueError`, invisible to a bare `except`; spec delta on
  `collector-to-map` and a README migration-log entry.

  **The historical migration-log entry was deliberately left wrong.** README's
  `redesign-collector-shape` entry illustrates interleaved downstream side
  effects with "e.g. `to_map`'s duplicate-key `ValueError`". That was true at
  that release. The log is read chronologically, so editing it would falsify
  history; the new entry states the current type and the old one keeps its own.

  **The tripwire held, with one honest exception.** 562 tests green,
  `git diff --stat -- tests/` naming exactly the two files the row predicted.
  But the row listed five `Counter` sites in `test_sink.py` and there were
  **six** — a nested `_CountingStatefulOp` at lines 371-372 that the read
  missed. It is in a named file and the import would not have resolved without
  it, so it was converted rather than escalated. The lesson is about the
  enumeration, not the tripwire: a grep would have found it and the row was
  built from a read.

  **Coverage went 98.05% -> 98.03%, and that is arithmetic, not a regression.**
  The task list said to treat a drop as a lost test, so it was investigated:
  missed statements (2), branches (288) and partial branches (26) are identical
  before and after, and the uncovered set is the same two lines in
  `_summarizing`. Total statements fell 1147 -> 1136 because the change deletes
  eleven *covered* statements, which raises the weight of a fixed uncovered
  remainder. **A pure-deletion change can lower a coverage percentage without
  uncovering anything** — worth remembering the next time this gate moves.

  `ruff`, `ruff format --check`, `ty check src` and
  `openspec validate --strict` all pass, plus a clean-interpreter
  `import snakestream` to rule out a cycle from `collector.py`'s new
  `exception` import. See `openspec/changes/tidy-collector-containers`.

- **`comparator.py` split out of `sort.py`** (2026-08-25). Story 5 of the
  2026-08-25 batch, and the last of the dependency chain. (Story 6, which
  nothing waited on, landed after it and closed the batch.)

  `sort.py` was named for one of the three things it held.
  `check_comparator_result_type` and `is_new_extremum` are comparator
  *semantics*, and their consumers — `_MinMaxSink` in `terminals.py`,
  `min_by`/`max_by` in `collector.py` — sort nothing, yet both imported them
  from a module called `sort`. That misdirection was the whole defect.

  **Two modules, not one, and that was the user's call.** The roadmap row's
  literal reading was to fold everything into one `comparator.py`, defensible
  since `comparator-contract` governs all five functions. Rejected because it
  renames around the defect rather than fixing it: one big `comparator.py`
  would leave `ops.py` importing a *sort dispatcher* from a module named
  `comparator` — the same misdirection pointed the other way. Split, each
  importer gets a module whose name is accurate for what it takes from it, and
  the already one-way dependency (sorting calls semantics; never the reverse)
  becomes a visible import edge instead of an implicit file ordering.

  **The row's open question — where `sort()` lands — was answered `sort.py`,
  on the rule that the seam belongs with the caller, not the definer.**
  `sort()` consumes comparator semantics exactly as `_checked` and `_merge` do.
  Putting it in `comparator.py` would have left that module owning a function
  whose only caller is `ops.py`, and `sort.py` reduced to `_checked` plus
  `merge_sort` with no entry point — a module nothing imports directly. The
  confirmation is `ops.py:15`: `from snakestream.sort import sort` reads
  correctly before and after, unchanged, and `_SortedSink.end()`'s comment
  naming `sort.py` stayed true. The decision that required no edit at the only
  external call site is the one that matched what was already there.

  **Beyond the story as written: `type.py` gained an alias, and `ty` is what
  forced it.** The plan said to annotate `merge_sort`/`_merge` with the
  `Comparator` union, reasoning it was a safe supertype and that adding a
  narrowed alias was a different story. That was wrong on a checkable fact.
  `Comparator` is `Callable[[T, T], int | Awaitable[int]]` and `_merge` awaits
  it unconditionally, so annotating turned the await into
  `invalid-await: int | Awaitable[int] is not awaitable`. The union is not a
  safe supertype where the body does something only the narrow arm supports.
  While the functions were bare, `ty` inferred nothing and said nothing —
  **annotating is what surfaced it**, which is the argument for closing out
  unannotated code rather than leaving it. Nothing else in the codebase hit
  this because every other comparator await goes through
  `_maybe_await`/`AsyncDispatch`, which return `Any`; `_merge` is the only site
  awaiting a `Comparator` directly. Resolved with one line in `type.py` —
  `AsyncComparator = Callable[[T, T], Awaitable[int]]` — and
  `cast("AsyncComparator", comparator)` at `sort()`'s two reroute sites, where
  `is_async_callable` or the trial comparison has just *proved* the narrowing.
  A `cast("Awaitable[int]", ...)` inside `_merge`'s loop was rejected: it
  states the narrowing at the least informative point and puts a cast on the
  per-comparison path. Flagged and user-approved rather than absorbed.

  **The annotation strand was an assumption, and it is worth recording as
  one.** The roadmap row named the module's bare functions, so the work was
  taken into scope without being confirmed. It paid for itself by finding the
  `Comparator` gap, but the precedent is the assumption, not the luck. `src/`
  now has **no unannotated function at all** (verified by `ast`, not grep).

  **A pure move, and the instruments say so.** 562 tests green with **no test
  file modified**, and coverage back at exactly **98.05%** — a move cannot
  shift coverage, so an unchanged number is the evidence nothing else happened.
  The `sort.py` diff is three hunks: one added import, the two removed
  functions, and one docstring phrase (`_checked`'s "the same trick
  is_new_extremum uses *above*", which the split falsified). `ruff`,
  `ruff format --check`, `ty check src` and `openspec validate --strict` all
  pass, plus a clean-interpreter `import snakestream` to rule out a cycle
  between the two new modules. No spec impact — `skip_specs: true`; every
  moved function kept its name, signature and body. See
  `openspec/changes/split-sort-into-comparator-and-sort`.

- **The sync-comparator fast path** (2026-08-25). Story 4 of the 2026-08-25
  batch, and the only one in it that makes the library faster rather than
  easier to read.

  `_SortedSink.end()` routed every comparator-based sort through `merge_sort`,
  and its own comment stated the cost as if unavoidable — *"Trades away
  Timsort's speed for sync comparators"*. Only the async case actually needs a
  hand-written merge with an `await` in its inner loop. `sort.py` gained one
  entry point, `sort(arr, comparator)`, which owns the choice: sync comparators
  now go to `list.sort(key=cmp_to_key(...))`, async ones to `merge_sort`.
  `_SortedSink.end()` calls `sort()` and says so in two lines instead of five.

  **Confirmed figures**, 20,000 random floats, sync 3-way comparator, best of
  9, Python 3.14.5: **69.4 ms -> 38.7 ms end-to-end through `sorted()`
  (1.8x)**, and **58.4 ms -> 27.5 ms measuring the sort alone (2.1x)**. The
  end-to-end number is the smaller one because the pipeline's own per-element
  cost is unchanged and now dominates a larger share. The async path is
  unaffected: 6.7 ms -> 6.8 ms on a 2,000-element async-comparator sort, within
  noise.

  **The 3.6x the proposal's table showed is not available, and the reason is a
  spec.** `comparator-contract`'s "Comparators must not return bool" makes
  `sorted()` responsible for raising `TypeError` on a `bool` result. A `bool`
  compares perfectly well under `cmp_to_key` — it is an `int` — so handing it
  the raw comparator would silently produce a wrong order instead of raising.
  `_checked()` keeps a per-comparison type test, inlined with a call-out only
  on the raising path, the same trick `is_new_extremum` already uses one
  function up. **1.3x is the price of the contract; the contract wins.**

  **The open question the roadmap left for this story — the one-time
  `isawaitable` safety net — was answered with a trial comparison.** A
  comparator with a plain `def __call__` returning a coroutine classifies as
  sync, and `list.sort` is sync all the way down, so a coroutine seen mid-sort
  cannot be awaited from inside the key function. `sort()` therefore makes one
  trial `comparator(arr[0], arr[1])` before the sort when classification says
  sync and the buffer holds two or more elements; an awaitable result is
  awaited (so nothing is left un-awaited) and the whole sort reroutes to
  `merge_sort`. The alternative the notes floated — documenting a narrowing for
  `sorted()` alone — was **rejected**: it would break `callable-dispatch`'s
  "Sync-signatured callable that returns a coroutine" scenario, which names no
  operation and so covers `sorted()`, and the
  `test_sorted_sync_call_returning_coroutine_comparator` test that pins it.
  The cost is one extra comparator invocation per comparator sort of two or
  more elements; nothing constrains the invocation count, and nothing could,
  since Timsort and merge sort make different numbers of comparisons on the
  same input anyway.

  **Beyond the story as written: `merge_sort` lost its `state` list, and
  branch coverage is what found it.** The plan said to leave `merge_sort`
  byte-for-byte alone. That could not hold — once `sort()` settles asyncness
  ahead of the call, *every* comparator reaching `merge_sort` returns
  awaitables, either because `is_async_callable` said so or because the trial
  proved it, so `_merge`'s `elif not state[1]` ladder can never fire. The
  suite stayed green and said nothing; the `branch-coverage-gate` at 98% is
  what caught it, as two unreachable arms dropping the total to 97.79%. The
  ladder and the `state` list are gone, `merge_sort` recurses into itself
  rather than into a `_merge_sort` that existed only to thread state, and
  `_merge` does a plain `await comparator(...)`. Ten lines lighter, and it now
  says what is true — *this function is the async path* — where the surviving
  ladder said the opposite. Same removal this batch made to
  `_ForEachSink._finish`.

  **One test added, no test modified.** Both bool-rejection tests now raise
  from the trial comparison, one comparison earlier, which left `_checked()`'s
  own `TypeError` line uncovered. `test_sorted_rejects_non_int_on_a_later_comparison`
  sorts `[3, 1, 2.5]` with `lambda a, b: a - b` — `int` for the trial pair
  `(3, 1)`, `float` once `2.5` is involved — covering the line and pinning a
  contract requirement the suite never asserted: the `int` contract holds for
  *every* comparison, not just the first.

  562 tests green, 98.05% coverage. `ruff`, `ruff format --check`,
  `ty check src` and `openspec validate --strict` all pass. No spec impact —
  `skip_specs: true`, since `sorted()`'s results, stability, `reverse`
  handling, `bool` rejection and async support are all unchanged. See
  `openspec/changes/sort-with-cmp-to-key`.

- **Chain-building and dead-code smalls** (2026-08-25). Story 3 of the
  2026-08-25 batch, and the last of its three `stream.py` stories. Four
  independent findings, one commit each, none of them observable.

  **(a)** The eight intermediate ops were each the same 90-column line —
  `cast("Stream[X]", self._derive(self._chain + [_SomeOp(...)], self._executor))`
  — so the chain-extension rule was written eight times while the one thing
  each method is *about*, the `Op` it queues, was the least visible part of
  the line. A private `_extend(op)` now holds
  `self._derive(self._chain + [op], self._executor)`, and each op is a
  one-liner: `return self._extend(_MapOp(mapper))`.

  `_extend` takes a **built** `Op` rather than the class plus its arguments.
  The eight `Op` constructors take between zero and two arguments of unrelated
  types (`_DistinctOp()` takes none, `_SortedOp` takes a comparator and a
  flag), so an `_extend(op_cls, *args)` form would degrade to `*args: Any` and
  lose exactly the type information the call site has. It also does not run
  `_check_not_consumed()` — `_derive()` already does, and duplicating the
  guard one frame up would make it ambiguous which one is load-bearing.
  `_derive_executor()` was deliberately left out: `parallel()`/`sequential()`
  pass `self._chain` **unchanged** under a different executor, the opposite of
  what `_extend` does, and folding both into one helper would re-couple what
  the batch's earlier stories separated.

  **Superseded 2026-08-26 by `collapse-derive-wrappers`:** `_extend` is gone,
  and so is `_derive_executor()`; there is one `_derive(op: Op | None = None)`.
  The ergonomic win described above survives intact — the call site is now
  `return self._derive(_MapOp(mapper))`, the chain-extension rule still lives
  in exactly one body, and the built-`Op`-not-class argument is unchanged and
  for the same reason. What changed is where the rule lives: in the copier
  itself rather than a wrapper over it, which is what let the executor axis
  leave the copier's signature instead of being passed through as noise.

  **Beyond the story as written: the eight `cast()` wrappers went too, and
  that is most of the win.** The `cast` was never necessary — `_derive()`
  returns `Stream[Any]`, and `Any` is assignable to each method's declared
  return type, so the cast narrowed nothing while reading like a real
  narrowing. Verified against the `ty` version CI runs on the 3.14 leg before
  committing to the shape, since `cast` is erased at runtime and no test can
  tell the two forms apart. The `cast` import stays: `sequential()`,
  `parallel()`, `iterate()` and the 3-arg `collect()` still use it.

  **(b)** `_ForEachSink._finish` deleted. `TerminalSink._finish` is
  `return container`, `_ForEachSink._create_container` is `return None`, and
  the sink assigns `self._container` nowhere else — so the override returned
  `None` for the one input on which the base already returns `None`. Recorded
  in the commit message because the override *looks* load-bearing: a reader
  who assumes `for_each` must discard a result will read it as the thing doing
  the discarding. It is not; `result()` being `None` comes from
  `_create_container`. The three other `_finish` overrides in `terminals.py`
  were checked and kept — each translates the `_UNSET` sentinel, which the
  base does not do.

  **(c)** `sorted(..., reverse: bool = False)`. `stream.py` now has no
  unannotated parameter at all (AST-checked, not eyeballed).

  **(d)** `asyncio.ensure_future` -> `asyncio.create_task` at both
  `race_through()` sites. The benchmark exemption was written as
  **conditional** rather than granted — it held only while the diff stayed a
  one-word substitution at each site, and it did: two lines, one word each,
  nothing else moved. Both arguments are `branch.__anext__()` on an async
  generator, always a coroutine, so `ensure_future`'s
  `isfuture`/`iscoroutine`/`isawaitable` ladder always landed on the coroutine
  arm and called its internal `loop.create_task` anyway.

  561 tests green, **no test file edited** — the entire verification story for
  a change with no new behaviour to assert. `ruff`, `ruff format --check`,
  `ty check src` and `openspec validate --strict` all pass, 98.03% coverage.
  No spec impact: the change set `skip_specs: true`, the same treatment as
  `split-ops-into-ops-module` and `collapse-terminal-drive-loop`. See
  `openspec/changes/tidy-stream-chain-building`.

- **Settled what counts as a source, and how a racing branch consumes one**
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

- **Settled `stream.py`'s API surface outside the chain: `iterate`, `concat`,
  `close`** (2026-08-25). Story 2 of the 2026-08-25 batch. Three independent
  edits, one commit each, landed in order so a bisect lands on one behaviour.

  **(a)** `Stream.iterate()`'s `nxt` was the one user-supplied callable in the
  library not routed through the `is_async_callable`/`isawaitable` dispatch
  shape every other callable uses — an `async def nxt` silently produced a
  stream of un-awaited coroutine objects:

  ```python
  async def nxt(x):
      return x + 1


  await Stream.iterate(1, nxt).limit(3).to_array()
  # [1, <coroutine object nxt>, <coroutine object nxt>]   -- no error raised
  ```

  `_make_iterator` is now an `async def` generator carrying the same
  `is_async`/`checked` locals as the canonical shape in
  `callable_dispatch.py`, and `nxt`'s type moved from `Callable[[T], T]` to
  the existing `Mapper[T, T]` — dispatched rather than pre-call-rejected
  (the `flat_map` shape), since an async `nxt` is not structurally impossible
  the way an async `flat_mapper` is, and rejection would still miss a
  callable object with an async `__call__`. New capability spec
  `stream-iterate`, covering the lazy seed/`nxt` sequence and all four
  sync/async function/callable-object forms — nothing had specified
  `iterate()`'s own contract before this.

  **(b)** `Stream.concat(a, b)` built its result with an empty close-handler
  list, discarding both operands' handlers. It now constructs the result with
  `a._close_handlers + b._close_handlers` — a fresh list, so registering a
  handler on either input after `concat()` returns does not retroactively
  reach the result — matching Java's `Stream.concat`, whose result closes
  both inputs. ADDED requirement on the `stream-concat` capability, a clean
  spec gap rather than a rule change.

  **(c)** `close()` collected every handler's exception but discarded every
  one except the first. It still raises the first — that rule is unchanged,
  pinned by the existing `test_close_with_multiple_raising_handlers_runs_all_and_raises_first`,
  verified to pass unmodified — but now attaches the later exceptions to it
  via `BaseException.add_note()` (Python 3.11+) in encounter order, so a
  traceback shows all of them. On 3.10 the behaviour is exactly what shipped
  before: first exception raised, no notes. `sys.version_info >= (3, 11)`
  narrows for `ty` without a cast, which `hasattr(exc, "add_note")` would
  not. MODIFIED requirement on `stream-close-handling`.

  **Tripwire held exactly as scoped:** the only test files touched are
  `tests/test_iterate.py`, `tests/test_concat.py` and `tests/test_close.py`,
  and the pinned multi-raise test needed no edit. 561 tests green (536 + 25
  new), `ruff`, `ruff format --check`, `ty check src` and
  `openspec validate --strict` all pass, coverage 98.03%. No benchmark gate:
  every site here runs once per stream, once per `concat()` call, or once
  per `close()` call, never per element — story 4 is the batch's only
  benchmark-gated story. README's `iterate` row now notes `nxt` may be sync
  or async; no migration-log entry, since the only call shape whose result
  changed was already producing garbage. See
  `openspec/changes/settle-stream-api-outside-the-chain`.

- **Took the final three-part smalls batch: `unordered()`/`on_close()`
  docstrings, the `PROCESSES` top-level export, and the dead `pylint`
  pragmas in `collector.py`** (2026-08-24). The last item of the 2026-08-24
  legibility batch, closing it out entirely.

  **(a)** `unordered()` (`stream.py:151`) and `on_close()` (`stream.py:158`)
  each gained a one-line docstring stating they mutate and return `self` by
  design, unlike the eight derive-and-consume intermediate ops — pointing at
  the `stream-ordering` spec and `pipeline-immutability` spec line 58
  respectively, the requirements that already made this deliberate.

  **(b)** `PROCESSES` is now exported from `snakestream/__init__.py`
  (`from snakestream.execution import PROCESSES as PROCESSES`), so
  `from snakestream import PROCESSES` works. Decided in favor of exporting
  rather than narrowing README, matching how README already documented
  `.parallel()`/`PROCESSES` as a stable public pair. New capability
  requirement added to `stream-execution-model` covering the import path;
  no README wording change was needed, and no existing top-level-exports
  table needed touching (none exists). Covered by a new
  `tests/test_package_exports.py`.

  **Superseded by `name-by-visibility-not-underscore` (2026-09-03, below):**
  the export is removed. It never was a tunable lever — `execution.py` binds
  `RACING` from `PROCESSES` at import time, so assigning to the exported
  name never changed the worker count — and the `stream-execution-model`
  requirement this added is the one that change's spec delta removes.
  `PROCESSES` keeps its name and value in `snakestream.execution`; only the
  two import paths are gone.

  **(c)** The four `# pylint: disable=missing-*-docstring` /
  `# pylint: disable=invalid-name` pragmas at the top of `collector.py`
  were confirmed dead (no `pylint` config or invocation anywhere in the
  repo — only comment pragmas, here and in two unrelated test files left
  out of scope) and deleted.

  536 tests green (535 + the new export test) with **no existing test file
  edited**; `ruff`, `ruff format --check`, `ty check src` and
  `openspec validate --strict` all pass, 98% coverage. Off the per-element
  path (docstrings are read not executed; the export and pragma removal are
  import-time/lint-time only), so no benchmark gate applied. See
  `openspec/changes/archive/2026-08-24-batch-small-fixes-2026-08-24`.

- **Added module docstrings to `execution.py`, `sink.py` and `ops.py`**
  (2026-08-24). All three opened straight into imports; the map that
  explains how the chain-of-ops model executes — the four execution
  primitives and the two executors, the op/sink `begin`/`accept`/`end`
  protocol, one `Op`/`Sink` pair per intermediate operation — lived only in
  `CLAUDE.md`, a file a reader opening any of the three directly might never
  see.

  Each docstring is four or five lines and orientation only, not a
  restatement of what the per-class docstrings in the same file already
  say: `execution.py` names `stream_through`/`race_through`/`feed_through`/
  `drain` and `Sequential`/`Racing`, and points at `Sequential.value()`'s
  docstring for the fused-push figures rather than repeating them;
  `sink.py` names the `Sink` protocol and the shapes built on it;
  `ops.py` states it holds no execution logic, which lives in
  `execution.py`.

  Pure documentation, `skip_specs: true`: no spec-level behavior changed,
  only what a reader sees before the imports. 535 tests green with **no
  test file edited**; `ruff`, `ruff format --check` and `ty check src` all
  pass. Off the per-element path (docstrings are read, never executed), so
  no benchmark gate applied. See
  `openspec/changes/add-execution-module-docstrings`.

- **Trimmed the `IllegalStateException` message to drop "or terminally
  consumed"** (2026-08-24). `stream.py:97` read "this stream has already been
  extended into a new instance **or terminally consumed**", but `_consumed =
  True` is only ever set by `_derive()`, the shared copier behind the eight
  intermediate ops and `.parallel()`/`.sequential()` — never by a terminal.
  `pipeline-immutability` spec explicitly requires a merely-terminally-consumed
  stream to stay usable, and `terminal-sinks` spec already worded the scenario
  without the "or terminally consumed" clause; only the exception string
  disagreed with both.

  One-line change to `_check_not_consumed()`, scoped to the message string.
  `skip_specs: true`: the specs already described the correct behavior, so
  nothing in `openspec/specs/` changed. No test asserts the message text
  (verified 2026-08-24 against all eight `pytest.raises(IllegalStateException)`
  sites across `test_pipeline_immutability.py` and `test_execution_model.py`),
  so 535 tests passed with **no test file edited**; `ruff`, `ruff format
  --check` and `ty check src` all pass. Off the per-element path (raised only
  on reuse of a consumed stream reference), so no benchmark gate applied. See
  `openspec/changes/archive/2026-08-24-fix-illegal-state-exception-message`.

- **Extracted a neutral `_ArgsOp` base for `StatelessOp`/`StatefulOp`**
  (2026-08-24). `StatefulOp`'s docstring spent a paragraph disclaiming its own
  base class — "Subclassing `StatelessOp` is a mechanical convenience ... It
  does not mean a stateful op is a kind of stateless one" — while the two
  classes shared only `__init__` and the `_sink_cls` `ClassVar` declaration
  and differed solely in `link()`. When a class docstring has to argue
  against the hierarchy it sits in, the hierarchy is misleading the reader,
  not the docstring.

  `sink.py` now has `_ArgsOp(Op)` holding the shared `__init__(self, *args)`
  and `_sink_cls` declaration, with `StatelessOp(_ArgsOp)` and
  `StatefulOp(_ArgsOp)` as siblings, each defining only its own `link()`.
  `StatefulOp` no longer subclasses `StatelessOp`, so the disclaimer
  paragraph is deleted rather than kept — its docstring now only explains
  what shared state is and how a subclass declares it. Both names stay
  importable and subclassable exactly as before, which is what
  `tests/test_sink.py`'s existing imports and subclasses of both exercise.

  Pure structural refactor, scoped to `sink.py`'s `Op` hierarchy alone;
  `ops.py`'s op definitions and every caller of `link()`/construction are
  unaffected. `skip_specs: true`: no spec-level behavior changed, only where
  two private class declarations sit in the hierarchy. 535 tests green with
  **no test file edited**; `ruff`, `ruff format --check` and `ty check src`
  all pass. Off the per-element path (`Op` construction and `link()` run once
  per composition, never per element), so no benchmark gate applied. See
  `openspec/changes/extract-op-base-class`.

- **Renamed `Stream._stream` to `Stream._source`** (2026-08-24). `stream.py`
  named the normalized `AsyncGenerator` source `self._stream`, while every
  function in `execution.py` that receives the same value (`stream_through`,
  `race_through`, `feed_through`, `_guarded`) names it `source` — reading
  `self._executor.elements(self._chain, self._stream)` required stopping to
  work out whether `_stream` was the raw source or something already
  composed. Now every call site reads as the `(chain, source)` pair the three
  execution primitives already take.

  Pure private rename, scoped to `stream.py`'s field declaration, `_derive`,
  `_compose` and `_evaluate` — the only methods referencing it after the
  `_evaluate()`/`_derive()` consolidations. `skip_specs: true`: no
  spec-level behavior changed, only an internal attribute's name. 535 tests
  green with **no test file edited** (a grep for `_stream` across `src/` and
  `tests/` confirmed zero references before archiving, matching the item's
  own prediction); `ruff`, `ruff format --check` and `ty check src` all pass.
  Off the per-element path (read once per composition or drive-entry), so no
  benchmark gate applied. See
  `openspec/changes/rename-stream-source-field`.

- **Routed every terminal through `_evaluate()`.** `_evaluate()`'s docstring
  called itself "the one place a stream's execution mode is consulted", but
  `for_each_ordered()` and `find_first()` each bypassed it and hand-rolled
  `self._check_not_consumed()` + `SEQUENTIAL.value(self._chain, self._stream,
  sink)` directly — three drive sites instead of one. `_evaluate()` gained an
  optional `executor: Executor | None = None` parameter
  (`(executor or self._executor).value(...)`); both terminals now read
  `await self._evaluate(sink, SEQUENTIAL)`.

  Landed exactly to the shape this entry's own implementation notes proposed,
  with no surprises: no behaviour changed (both terminals still force
  sequential/ordered execution regardless of the stream's mode,
  `find_first()`'s `is_ordered()` short-circuit to `find_any()` untouched),
  and the `stream-find-first` spec's wording ("achieve this by naming the
  sequential executor explicitly for that drive") held verbatim against the
  new call shape — checked directly, no edit needed. `skip_specs: true`: no
  spec-level behavior changed, only how many places decide which executor
  drives a terminal. 535 tests green with **no test file edited**; `ruff`,
  `ruff format --check`, `ty check src` and `openspec validate --strict` all
  pass. A grep for `self._stream` after the edit confirms only `__init__`,
  `_derive`, `_compose`, `_evaluate` and `_derive_executor` reference it now —
  `for_each_ordered()` and `find_first()` were the only two hand-rolled call
  sites, and both are gone. See
  `openspec/changes/route-terminals-through-evaluate` (pending archive).

- **Merged `_derive()` and `_derive_executor()` into one copier** (2026-08-24).
  `stream.py:99-106` and `stream.py:132-137` were line-for-line the same
  five-field copy — `self._stream`, `self._close_handlers`, `self._chain`,
  `self._ordered`, `self._executor` — differing only in whether `_chain` or
  `_executor` was the field that varied. Now one `_derive(self, chain:
  list[Op], executor: Executor) -> Stream[Any]` takes both as parameters: the
  eight intermediate ops call `self._derive(self._chain + [op],
  self._executor)`, and `parallel()`/`sequential()` call
  `self._derive(self._chain, RACING)` / `self._derive(self._chain,
  SEQUENTIAL)`. `_derive_executor()` is gone.

  Landed to the shape the roadmap's own implementation notes proposed, with
  one adjustment: the pre-existing `_derive()` took a single `op: Op` and
  composed `self._chain + [op]` internally rather than taking a pre-built
  chain, so the call sites (not just the method body) needed the `self._chain
  + [op]` expression moved onto them — the unified signature is
  `_derive(chain, executor)` exactly as designed, only the caller-vs-callee
  split of that one line differs from the sketch. The check-before-copy /
  consume-after-copy ordering is unchanged: `_check_not_consumed()` still runs
  before the copy and `self._consumed = True` still after, so a raising copy
  leaves the receiver valid. The `_derive_executor()` docstring ("must not
  compose", "must not assign onto self") moved onto `parallel()` and
  `sequential()` rather than being deleted with the method, since those two
  are the only call sites its warning actually protects.

  535 tests green with **no test file edited**; `ruff`, `ruff format --check`
  and `ty check src` all pass. A grep for `_derive_executor` across `src/` and
  `openspec/specs/` after the edit returns nothing. `skip_specs: true`: no
  spec-level behavior changed, only where the copy-constructor logic lives.

  **Superseded 2026-08-26 by `collapse-derive-wrappers`.** This merge was
  reverted on 2026-08-25/26 and has now been redone in a different shape, so
  read the two costs it paid rather than the signature it landed. The copier
  takes the `Op`, not a pre-built chain — `_derive(op: Op | None = None)` —
  which is what keeps the nine call sites one-liners instead of spelling the
  chain-extension rule out nine times, the cost that brought `_extend` back.
  And the docstring is not copied onto both public methods, which is the cost
  that brought `_derive_executor()` back: it sits on `sequential()` alone.
  Off the per-element path (chain-building/mode-switch code, run once per
  composition), so no benchmark gate applied. See
  `openspec/changes/unify-derive-copier`.

- **Moved `to_collection()`'s private `_C` TypeVar and `_SupportsAdd`
  protocol from `collector.py` to `type.py`** (2026-08-24). The last public
  collector signature naming a type outside `type.py`, the project's
  established home for shared callable/composite type aliases —
  `to_collection(collection_supplier: Supplier[_C]) -> Collector[Any, _C,
  _C]` kept `_C`/`_SupportsAdd` defined locally instead. Deliberately left
  alone on 2026-08-21 when the other 18 collector factories widened their
  accumulator parameter to `Any`, because here `A` genuinely is the caller's
  own container type rather than an internal box, so `_C` had to move rather
  than be erased.

  Pure relocation, both names moved together as a pair since `_C`'s bound is
  `_SupportsAdd`: `to_collection`'s signature and behavior are unchanged, and
  both stay private (leading underscore) and unexported — a caller never
  writes `_C` themselves, the checker infers it. Full suite green (535
  tests) with **no test file edited**, `ruff`, `ty check src` and `openspec
  validate --strict` all pass. `skip_specs: true`: no spec-level behavior
  changed, only where two private type declarations live. See
  `openspec/changes/archive/2026-08-24-move-to-collection-typevar-to-type-module`.

- **Collapsed `BaseStream` into `Stream`; `base_stream.py` is gone**
  (2026-08-24). The split existed because Java needs `BaseStream` as the shared
  parent of `Stream`/`IntStream`/`LongStream`/`DoubleStream`. This library never
  implemented the primitive specializations, and after the `ParallelStream`
  retirement below there was exactly one concrete subclass left — so the
  two-level tree held state on one class and operations on the other for no
  remaining reason. Exactly what the guiding principle targets: Java structure
  with no remaining Python reason to exist.

  **The roadmap entry demanded confirmation rather than assumption, and got
  it.** `BaseStream` was never exported from `__init__.py`; nothing in `src/` or
  `tests/` did `isinstance(x, BaseStream)` or subclassed it directly — the
  README's documented subclassing use case (wrapping an I/O-like resource via
  `on_close()`) already subclasses `Stream`; and the one test dependency on the
  split, `tests/test_sequential.py`'s `from snakestream.base_stream import
  _wrap_sink`, turned out to be importing a re-export of `execution.py`'s
  `_wrap_sink` rather than anything `base_stream.py` defined — a one-line
  import-path fix, not a behaviour edit.

  `Stream` is now `Generic[T]` directly, with every merged method keeping its
  signature and behaviour. README's separate `### BaseStream` API table was
  merged into `### Stream` (both always listed instance methods of the same
  runtime class), and `CLAUDE.md`'s architecture section, which attributed
  `self._stream`/`self._chain`/`self._executor`/`self._consumed` and the
  AutoClose pair to `BaseStream`, now describes `Stream`. Full suite green with
  that single import-path edit as the only test change; `ruff`, `ty` and
  `openspec validate --strict` all pass. The one surviving `BaseStream`
  reference in `openspec/specs/` is deliberate: `stream-ordering`'s Purpose
  cites *Java's* `BaseStream.unordered()` as the mirrored API. See
  `openspec/changes/archive/2026-08-24-collapse-base-stream-into-stream`.

  **Opened the 2026-08-24 legibility batch** now sitting at **Now** items 2-8:
  with the state and the operations finally in one file, reading `stream.py`
  end-to-end surfaced the three-drive-sites/one-docstring mismatch, the
  duplicated derive bodies and the `_stream`-vs-`source` naming split.

- **Retired the `ParallelStream` name from the specs and docstrings**
  (2026-08-24). `replace-parallel-stream-with-executor` deleted the class on
  2026-08-21 but not the name: two requirements whose deltas were never written
  or were missed by a truncated scan, ten spec `## Purpose` sections (a delta
  cannot touch Purpose — OpenSpec ignores `MODIFIED` blocks against it, so
  these needed direct edits), five docstrings in `sink.py` and
  `callable_dispatch.py`, and four scenario titles kept back because a
  `MODIFIED` block may not drop a scenario name the main spec still has.

  No behaviour gap anywhere in it — every described behaviour was correct and
  covered throughout — which is what made it worth one pass rather than a leak
  across several commits: readability debt of the misleading kind, where a
  reader grepping for `ParallelStream` found specs and docstrings promising a
  class the codebase no longer had. `grep -rn ParallelStream openspec/specs/
  src/` now returns nothing. Full suite green with **no test file edited**.
  Out of scope deliberately, and still true today: test-file comments and
  section headers, and the README migration-log entry that has to name the
  retired class to explain what was retired. See
  `openspec/changes/archive/2026-08-24-retire-parallelstream-name`.

- **Replaced the `Stream` -> `ParallelStream` subclass with execution mode as a
  value, and made `.parallel()`/`.sequential()` position-independent.** These
  landed together because they are mechanically the same edit: the
  compose-and-handoff is what carried mode as a type *and* what made the
  switches positional.

  **The exploration changed the shape of the item before it was proposed.** It
  had been framed as an internals cleanup — inverted default/override, two
  dispatch seams, an import cycle. Tracing `.parallel().map(f).count()`
  end-to-end surfaced two things the entry had not:

  *One name carried two meanings.* `_drive_to_sequential()` was both the fused
  fast path (performance) and "force encounter order, ignore the stream's mode"
  (semantics, used by `for_each_ordered` and `ParallelStream.find_first`). They
  shared an implementation by coincidence, so reading
  `ParallelStream.find_first() -> _drive_to_sequential()` gave no way to tell
  which was meant. They are now separate: the fast path is an implementation
  detail of `Sequential`, and forcing order is `SEQUENTIAL.value(...)` written
  at the call site.

  *`.parallel()` was position-dependent and Java's is not.* Because `_handoff()`
  composed the chain-so-far into a generator, ops declared before the switch
  were frozen under the old mode. Measured, 8 elements through a 100 ms async
  mapper: `.parallel().map(slow)` took 0.20s, `.map(slow).parallel()` took
  0.81s — identical to fully sequential. Java's `AbstractPipeline.parallel()` is
  `sourceStage.parallel = true; return this;`, a flag on the source stage, so
  the whole pipeline is affected wherever the call appears. With 1:1 public API
  parity as this project's first priority, that made it an API divergence rather
  than an internals detail. After the change both forms take 0.20s. **Note this
  inverts the trap the old roadmap entry warned about** — it cautioned that
  flipping a flag instead of handing off would "silently change semantics",
  which is true, but the semantics it changes *to* are Java's. What survived
  from that warning is the immutability half: the switch must still return a new
  instance and consume the receiver, so it is `_derive_executor()`, never
  `self._executor = X; return self`. **Superseded 2026-08-26 by
  `collapse-derive-wrappers`:** `_derive_executor()` no longer exists.
  `sequential()`/`parallel()` now derive with no op and assign `_executor`
  themselves, and the immutability rule this entry states is unchanged — it
  lives on `sequential()`'s docstring, at full length precisely because that
  body is one line away from the forbidden in-place flip.

  **Racing was kept deliberately, not by omission.** Partition-plus-combine
  (spliterator splits, per-partition pipelines, a `combiner` merge) was explored
  and set aside: Java's own answer for a non-splittable source
  (`Spliterators.IteratorSpliterator.trySplit()`, which drains a growing batch
  into an array) trades latency-to-first-element for throughput, which is the
  wrong trade for an async/IO-first library where racing yields an element the
  instant any branch produces one. The rule adopted: **Java is the public-API
  contract, not the implementation blueprint.** Partitioning, `spliterator()`
  and combiner wiring stay in **Later**.

  **The one asymmetry in the new protocol is there on measurement.**
  `Executor.value()`'s generic default is `drain(elements(...), terminal)`,
  which `Racing` inherits unchanged; `Sequential.value()` overrides it with the
  fused push. The task list put a gate before the design was allowed to keep
  that override, and it came back far larger than the +10-50% band the
  flush-dedup measurements had set as the expectation (Python 3.14.5, 20,000
  elements, no intermediate chain, best of 5, ns/element):

  | Variant | Fused | Generic | Delta |
  |---|---|---|---|
  | `count()` | 303 / 296 / 320 | 669 / 664 / 745 | **+125%** |
  | `reduce(acc)` sync | 353 / 351 / 348 | 745 / 739 / 775 | **+112%** |

  More than twice the cost per element, because this removes the async-generator
  round trip entirely rather than adding one object to a loop that already had
  one. The override stays and carries these figures in its docstring.

  **What went away:** `ParallelStream` and `parallel_stream.py`; `_drive`,
  `_drive_to`, `_drive_to_sequential`, `_parallel` and `_handoff`; both dispatch
  seams, replaced by `_compose()` and `_evaluate()`, one line each; the
  `stream.py` <-> `parallel_stream.py` import cycle and its two function-local
  import workarounds; `ParallelStream.find_first()`, unified into one
  implementation selecting on the ordering flag; and one generator layer per
  element on parallel pipelines, since a mode switch no longer composes
  (`.parallel().map(f).count()` went from five async-generator frames to four).
  **What arrived:** `execution.py` with four primitives, two executors and
  `PROCESSES`. It also **fixed a live bug**: `.parallel()`/`.sequential()` were
  the only ops in the library that discarded a `Stream` subclass and its
  attributes, despite CLAUDE.md documenting subclassing as supported.

  **The "green with no test edited" tripwire could not apply** — the behaviour
  change is the point — so it was replaced with a diff check: only the test
  sites identified *before* any source edit were allowed to differ. The
  pre-analysis found 51 `.parallel()` sites across 17 files, zero with an op
  before `.parallel()` on the same line, and four multi-line chains that change
  what runs raced. All four assertions were predicted to survive, and did; the
  two in `test_close.py` passed untouched. The two in `test_sequential.py` and
  `test_parallel.py` were rewritten rather than patched, because they tested
  mid-chain mode switching — a concept this change retires — and their names
  were already inverted relative to what they did. They now assert the new rule
  by timing, the same measurement that found the divergence. 535 tests green,
  coverage 98.08%. One new capability (`stream-execution-model`) and 11 spec
  deltas. See `openspec/changes/replace-parallel-stream-with-executor`.

  **Two decisions resolved along the way, recorded so they are not re-opened.**
  `Racing` holds `workers` as a field, which makes a public `.parallel(n)`
  trivially available — **deliberately not exposed**, because Java has no such
  overload and 1:1 surface parity is the first priority. Tune `PROCESSES`
  instead. And `unordered()` **stays a stream flag rather than moving onto the
  executor**: the executor answers *how* a pipeline runs, the flag answers
  *whether the caller requires encounter order*. Folding the flag in would mean
  `Racing` needed ordered and unordered variants, which is how `find_first()`
  ends up with two implementations again — the exact thing this change removed.

  **Left open deliberately:** whether `BaseStream` should collapse into `Stream`
  now that `ParallelStream` is gone. Java has `BaseStream` because
  `IntStream`/`LongStream`/`DoubleStream` share a parent; this library has no
  primitive specializations and already collapsed that distinction, so the split
  may be organizing nothing. It roughly doubles the diff and is independently
  revertable, so it is a follow-up rather than part of this change.

- **Took the small-cleanups batch: `to_list` as a factory, the race loop's
  per-element scans, `_maybe_aclosing`, and private box types in public
  signatures.** Four independent edits, three behaviour-neutral and one a
  public-API break, landed as one change with each part revertable on its own.

  **(a) `to_list` is now a factory, `to_list()`** — it was the single bare
  `Collector` instance in the public surface, so the API read
  `collect(to_list)` next to `collect(to_set())` for two equally stateless
  collectors. The direction was the real decision: the inconsistency could
  equally have been resolved by making `to_set` an instance, and both are
  breaking. Chose the factory because Java's `Collectors.toList()` and
  `toSet()` are both factories, and because it makes the rule statable without
  an exception — *every collector in `collector.py` is a factory* — where the
  reverse would have required callers to know which collectors are stateless.
  A callable-`Collector` shim keeping both forms working was rejected for the
  same reason `concat`'s `__await__` shim was: it makes the type permanently
  worse to spare a one-line migration. It breaks loudly — the bare name is a
  function, not a `Collector`, so an unmigrated call site hits the existing
  `collect()` guard and raises `StreamBuildException`. 151 call sites in the
  tests moved; `grouping_by`/`partitioning_by`'s `downstream` default is now
  `to_list()` evaluated once at definition time, which the "one instance is
  safe to reuse" property (still true, now pinned as a spec scenario rather
  than used as a justification for the shape) makes safe. Migration-log entry
  added; README gained a `to_list()` row it never had.

  **(b) The race loop's per-element list and linear scan are gone** —
  `any([n is not None for n in tasks])` allocated a throwaway list per
  iteration and `tasks.index(task)` was an O(branches) equality scan per
  element. Both collapse into one `{task: branch}` dict that doubles as the
  waitlist and as the "any branch still running" test, so the `tasks` list and
  its `None` holes disappear entirely rather than being kept alongside a
  counter. **Measured, per the standing rule, and the honest answer is no
  measurable win** (Python 3.14.5, 20,000 elements, no intermediate chain,
  best of 5, three invocations, driving `_parallel()` directly): `processes=4`
  6666/6712/6695 -> 6405/6631/6674 ns/element, a -1.0% median; `processes=16`
  5057/5054/5137 -> 5020/5016/4996, -0.8%. Both inside noise and clear of the
  no-regression gate. The absolute numbers say why: at ~6.7 microseconds per
  element the cost is `asyncio.wait()`'s own per-call set construction and
  scheduling, three orders of magnitude above a 4- or 16-entry scan. Kept for
  the clarity and the removed bookkeeping, not for throughput — recorded here
  so it is not re-proposed as a performance item.

  **(d) `_maybe_aclosing` is a 5-line `@asynccontextmanager`**, down from a
  14-line class. The `try`/`finally` is load-bearing and was the one real trap:
  without it the source leaks on every path that does not run to exhaustion.
  Three existing tests already covered the early-`break` paths (`flat_map`
  short-circuit, `any_match`, `find_first`) — verified by removing the
  `finally` and watching them fail — but **nothing covered the exception
  path**, so a test was added first and confirmed to fail without the
  `finally` before the rewrite landed.

  **(e) No private accumulator box is reachable from a public signature** —
  `summing_int() -> Collector[Any, _SumBox, int]` and 17 siblings widen their
  `A` parameter to `Any`. `T` and `R`, the parameters callers reason about,
  are untouched, and the private helpers (`_summing`, `_averaging`,
  `_summarizing`, `_extremum`) keep their precise box types, since that is the
  internal contract the checker should still see. `to_collection`'s
  `Collector[Any, _C, _C]` was deliberately left alone: there `A` genuinely is
  the caller's own container type, not an internal box.

  Parts (b), (d) and (e) held the "green with no test file edited" tripwire —
  the only test-file change outside part (a)'s mechanical rename was the new
  close-on-exception test. 518 tests green, coverage 98%. Eight capabilities
  took deltas, six of them (`collector-mapping`,
  `collector-collecting-and-then`, `pipeline-immutability`, `stream-iterator`,
  `terminal-sinks`, `generic-stream-typing`) only because their scenario text
  quoted the bare `collect(to_list)` form. See
  `openspec/changes/batch-small-cleanups`.

- **Dropped the pointless `async` on `Stream.concat`.** `concat` was an
  `async def` whose body never awaited anything — it built `_concat(a, b)`, an
  async generator (so *calling* it runs none of its body), and wrapped it in a
  `Stream`. The `async` bought nothing and cost every caller an `await` that
  could not suspend, plus the requirement to be inside a coroutine to call it
  at all. It is now a plain `def`, matching the other four static factories
  (`of`, `empty`, `builder`, `iterate`) and Java's static `Stream.concat`.

  **The one real decision was clean break vs. compatibility shim.** A `Stream`
  subclass with `__await__` returning itself would have kept both call forms
  working through a deprecation window; rejected because it puts an
  `__await__` on a `Stream` either permanently or until a *second* breaking
  change removes it, making the type worse than the one being fixed. The
  project's pre-1.0 convention is a hard break plus a migration-log line
  (`stream_of()` -> `Stream.of()`, the `Stream.of()` kwargs removal, the
  `str`/`bytes` change), and that is what this took. No custom error either:
  an unmigrated call site raises `TypeError: object Stream can't be used in
  'await' expression`, which names the exact expression at fault, and a bespoke
  `StreamBuildException` would have needed the rejected `__await__` to raise
  from.

  Scope stayed at one line of `src/`: `_concat`, the generator bridge, and the
  `_consumed` bookkeeping are all untouched, so `concat` still leaves both
  input streams unconsumed. A variadic `concat(*streams)` was named a non-goal
  rather than left open — Java's is two-arg. Seven tests added in
  `tests/test_concat.py` on top of the two existing ones dropping their
  `await`: returns a `Stream` rather than a coroutine, `await` on the result
  raises `TypeError`, callable from plain sync code with no running loop,
  empty input on either side, and both laziness properties checked through
  `peek` (nothing pulled at construction; the second stream untouched while
  the first is being consumed). Those last two codify behaviour that was
  already true — worth pinning precisely because the removed `async` is what a
  reader might mistake for the source of the laziness.

  Also corrected by omission: README's API table row for `concat` already
  listed the return type as `Stream` while sibling rows mark awaitables
  explicitly (`collect` reads `R (awaited)`), so the row was wrong before this
  change and is right now — no edit needed. New spec capability
  `stream-concat`; nothing in `openspec/specs/` covered `concat`'s own
  behaviour before, only `terminal-sinks`' note that it composes through the
  generator bridge, which still holds verbatim. 512 tests green, coverage
  98.20%. See
  `openspec/changes/archive/2026-08-21-drop-async-on-concat`.

- **Measured and rejected: collapsing `Stream.min`/`max`, `count` and `reduce`
  onto the `min_by`/`max_by`, `counting()` and `reducing()` collectors.**
  The duplication was real — `_MinMaxSink` and `_extremum` were the same
  algorithm down to a verbatim copy of the comparator-contract comment,
  `_CountSink` and `counting()` the same `+= 1`, `_ReduceSink` and
  `reducing()`'s two-arg form the same `_UNSET`-seed fold — and the collapse
  was implemented in full to find out what it cost.

  **Equivalence is not in doubt**, which is what makes the rejection a pure
  cost decision. With all three terminals routed through `collect(...)` and
  the three sinks deleted, the **whole 505-test suite passed with no test file
  edited**, and a separate 21-case audit (empty sources, singletons, falsy
  identities, first-of-tied tie-break, the `bool`-comparator `TypeError`, async
  callables, and all three on a `ParallelStream`) found **zero** differences
  between the two forms.

  **Killed on measurement at the gate the change's own tasks placed after the
  collapse.** Both forms are public API today, so baseline and collapsed ran
  interleaved in one process against the same source — a tighter comparison
  than the usual edit-and-remeasure. Harness otherwise as established (Python
  3.14.5, 20,000 elements, best of 5, three independent invocations), with one
  deliberate change: **no intermediate chain**, since here the terminal is the
  subject and an empty chain maximizes its share of per-element cost. Gate was
  +10% on the sync variant, the level `collapse-terminal-drive-loop` already
  treated as real:

  | Variant | Baseline ns/element | Collapsed ns/element | Median delta |
  |---|---|---|---|
  | `count()` | 298 / 306 / 299 | 360 / 332 / 357 | **+19.6%** |
  | `min(cmp)` sync | 467 / 442 / 422 | 608 / 560 / 522 | **+26.5%** |
  | `min(cmp)` async | 558 / 551 / 513 | 648 / 626 / 651 | +16.2% |
  | `reduce(acc)` sync | 332 / 356 / 354 | 622 / 562 / 601 | **+69.6%** |
  | `reduce(0, acc)` sync | 369 / 331 / 355 | 630 / 590 / 601 | **+70.6%** |
  | `reduce(acc)` async | 454 / 468 / 466 | 657 / 720 / 714 | +53.3% |

  All three failed, so all three took the fallback. The cause is the same one
  `add-callsite-dispatch` established: a `Collector` must be reusable across
  concurrent collections, so its per-collection dispatch state lives on a
  supplier-made box reached through a Python-level `async def` call, where a
  sink has it inline on `self`. `reduce` is worst by a wide margin because
  `reducing()` additionally routes every element through `_classify_step`,
  which is a function call plus a tuple allocation and unpack per element per
  callable — precisely the cost `optimize-callable-dispatch` hoisted out of the
  per-element path in the first place.

  **What landed instead — the per-terminal fallbacks, all behaviour-neutral,
  505 tests passing unedited at 98.20% coverage:**

  - **`min`/`max`: the shared rule was extracted, and it made both sides
    faster.** `sort.py` gained `is_new_extremum(sign, asc)`, holding the
    comparator-contract check, the sign test and the first-of-tied rule — the
    part that had been duplicated verbatim — called by both `_MinMaxSink` and
    `_extremum`. It *replaces* their existing `check_comparator_result_type()`
    call rather than adding a second one, and inlines the `type(sign) is not
    int` test so only the raising path calls out. Net one fewer Python-level
    call per element: `min` sync went **442 -> 404 ns/element**. (Delegating to
    `check_comparator_result_type` instead of inlining the test measured ~5%
    slower, which is why it does not.)
  - **`count`: roadmap item 2(c) taken as the fallback.** `_CountSink` now
    accumulates into a plain `int` instead of a `Counter` box, since the sink
    owns its container exclusively — 300 vs 299 ns/element, i.e. neutral on
    time, with one allocation and one indirection gone. `counting()` keeps its
    box, which it genuinely needs: its accumulator is a free function that has
    to mutate a container it was handed. `Counter` itself stays regardless —
    `ops.py`'s `_LimitOp` and `_SkipOp` use it as state shared across a
    `ParallelStream`'s branches, the case a plain `int` cannot serve.
  - **`reduce`: cross-referenced, not merged.** The shared part is the
    `_UNSET`-seed rule and the empty-finishes-as-`None` rule — two lines and a
    comment, not an extractable function. `_ReduceSink`'s docstring and
    `reducing()` now each point at the other, recording that the duplication is
    deliberate and measured and that a change to either rule belongs in both.

  **Consequence:** routing these terminals through a `Collector` is now a
  deliberately-accepted cost with numbers behind it rather than an open cleanup
  item, and should not be re-proposed without new evidence — the same posture
  `add-callsite-dispatch` established. The narrower reading that *did* pay off
  is worth keeping in mind: extracting a **sync** helper that replaces an
  existing per-element call is free or better, while anything adding a
  coroutine frame or a box to the per-element path is not. `stream.py` is
  untouched; `README.md` changed only in the `min_by`/`max_by` rows, whose
  "Wraps `Stream.min()`'s existing logic" wording is now "shares the rule
  with", which is what the code actually does. See
  `openspec/changes/collapse-terminal-collector-duplication`.

- **Collapsed the two terminal drive loops into `_copy_into()`.**
  `BaseStream._drive_to_sequential()` and `ParallelStream._drive_to()` each
  spelled out the same begin / cancellation-guard / accept-loop / end sequence;
  both now call a module-level `_copy_into(head, src, state_map)` in
  `base_stream.py`, named after Java's `AbstractPipeline.copyInto()` the way
  `_wrap_sink()` is named after `wrapSink()`. The pre-first-pull guard's
  reasoning — a chain can already be cancelled before it has seen anything
  (`limit(0)`) — now has one home instead of being a comment in one of three
  copies. `ParallelStream._drive_to()`'s `_maybe_aclosing` scope widened to
  cover the whole drive, matching the sequential form; the only delta is
  constructing (never starting) the composed generator on the already-cancelled
  path, verified to start no task and leave nothing pending. Two source files,
  +21/-19 lines, no test assertion changed (two stale comment references in
  `tests/test_sink.py` were repointed at `_copy_into()`), coverage 98.15% ->
  98.21%. **No README edit was needed**: every name involved — `_copy_into`,
  `_drive`, `_drive_to`, `_drive_to_sequential`, `_maybe_aclosing`,
  `_wrap_sink` — is private and unexported, and no parity table entry changes.

  Folded in before archiving: `_compose()` gained the docstring it was missing.
  It is the third member of the dispatching/overridden family alongside
  `_drive_to` and `_drive_to_sequential` — the seam where execution mode is
  decided, which `ParallelStream` overrides to fan the chain into a race — and
  it was the only one not saying so, which made it read as a pointless
  delegation to `_drive()`. `_drive()` cannot be that seam: `_parallel()` calls
  it once per racing branch, so overriding it would make each branch fan out
  again.

- **Rejected: deduplicating `BaseStream._drive()`'s bridge-buffer flush block.**
  The same roadmap item proposed a local closure for the two verbatim four-line
  flush blocks at `base_stream.py:120-123` and `127-130`. `_drive()` has to
  `yield` mid-loop, so it cannot use `_copy_into()` at all, and every
  single-flush-site form puts a per-element object on the `iterator()` /
  `to_generator()` / parallel-branch path — the in-loop flush runs once per
  element; only the post-`end()` flush is once per stream. Measured on the
  established harness (Python 3.14.5, 20,000 elements, chain of 8 `.map()` ops,
  best of 5, three independent invocations), baseline reproducing the
  1,907 ns/element `add-callsite-dispatch` recorded:

  | Variant | ns/element (3 runs) | vs baseline |
  |---|---|---|
  | **Baseline** — duplicated block, as shipped | 1929, 2091, 1907 | — |
  | Single site via **async-generator** closure | 3002, 2932, 3009 | **+50%** |
  | Single site via **sync-generator** closure | 2137, 2123, 2217 | **+10%** |

  This is the same trade `GeneratorBridgeSink`'s docstring already records
  rejecting for a `drain()` returning a fresh list. By contrast `_copy_into()`,
  entered once per stream, measured free: 1686/1620/1741 baseline vs.
  1625/1654/1739 with the helper on a `count()` terminal — noise in both
  directions. **Do not re-propose the flush dedup without new figures.**

- **Fixed the dead `__next__` branch in `_normalize()`.** The guard admitted a
  source on `hasattr(source, "__iter__") or hasattr(source, "__next__")` while
  the body was `for i in source`, so a sync iterator implementing only
  `__next__` passed the guard and then died with `TypeError: 'X' object is not
  iterable`. **Decided to make the advertised support real rather than narrow
  the guard**, because three things already promised it and only the code
  disagreed: README lists `Iterator` among accepted sources, the
  `stream-construction` spec's "Iterable source spreading" requirement names
  `__next__` explicitly, and `_maybe_aclosing`'s docstring exists precisely so
  a bare `__anext__`-only async iterator works — narrowing would have meant
  retracting a capability in all three and leaving the sync and async sides
  deliberately asymmetric.

  `__iter__` is still checked first, so lists, tuples and every other plain
  iterable run exactly the code they did before (`next([1, 2, 3])` is a
  `TypeError`, so one merged path was never an option); the new arm only
  catches sources with `__next__` and no `__iter__`. The non-obvious part is
  PEP 479: a `StopIteration` escaping an async generator body surfaces as
  `RuntimeError: async generator raised StopIteration`, so the loop guards the
  `next()` call alone and keeps the `yield` outside the `try` — which also
  means a `StopIteration` thrown in at the yield still propagates instead of
  being swallowed into a silent end-of-stream.

  Behaviour-preserving for every source that worked before; the only sources
  whose behaviour changed are ones that raised `TypeError`. No public API
  change, so no migration-log entry. Seven tests added in
  `tests/test_normalize.py`, including an `assert not hasattr(obj, "__iter__")`
  guard so they can't drift onto the `__iter__` path, the immediately-exhausted
  case that covers the `except StopIteration` arm, and a laziness check that
  `limit(2)` advances the source exactly twice. See
  `openspec/changes/archive/2026-08-20-fix-next-only-source-normalization`.

- **Added the four remaining Java 8 `Collectors`** — `mapping(mapper,
  downstream)`, `collecting_and_then(downstream, finisher)`,
  `summarizing_int`/`summarizing_long`/`summarizing_double`, and
  `to_collection(supplier)`. `mapping`/`collecting_and_then` are
  downstream-adapting collectors built on the same downstream-`Collector`
  composition `grouping_by`/`partitioning_by` already used; the `summarizing_*`
  trio shares the `_summing` dispatch idiom and finishes to a new
  `SummaryStatistics` `NamedTuple` rather than Java's mutable
  `IntSummaryStatistics` — with `min`/`max` as `None` on an empty stream,
  following `min_by`/`max_by`'s convention here instead of Java's sentinel
  ints; and `to_collection` generalizes `to_list`/`to_set` to any
  `add()`-supporting container. Additive, no public API change. This closes out
  Java 8 `Collectors` parity, and unblocked the min/max/count/reduce collapse
  that was a **Now** item at the time — since implemented in full, measured,
  and rejected on cost (see the entry above). See
  `openspec/changes/archive/2026-08-20-add-remaining-java8-collectors`.

- **Redesigned `collector.py`'s collectors around a `Collector(supplier,
  accumulator, combiner, finisher)` shape**, matching Java's `Collector<T,A,R>`
  interface. Every factory (`to_list`, `joining`, `counting`, `summing_*`,
  `averaging_*`, `min_by`/`max_by`, `reducing`, `to_map`, `to_set`,
  `grouping_by`, `partitioning_by`) now returns a `Collector` instead of a
  monolithic `async def _collect(composition): async for n in composition:
  ...` closure, driven through one new `_CollectorSink` (`TerminalSink`
  adapter) rather than each factory hand-rolling its own drain loop. This
  deletes the second, independent implementation of `terminals.py` that
  `collector.py` used to carry: `_extremum` (gone, replaced by a shared
  `_extremum` collector factory using the same tie-break and
  comparator-guard as `_MinMaxSink`), the duplicate `_UNSET` sentinel (now
  one, in `sink.py`), and the separate counting/reducing bodies.

  Two **BREAKING** changes, both pre-1.0 and both contained — no test in the
  457-test suite exercised either pattern: `collect(collector)` now requires
  a `Collector` (or `to_generator`, wrapped as the one `StreamingCollector`
  exception) rather than an arbitrary callable, and `grouping_by`/
  `partitioning_by`'s `downstream` now requires a `Collector` too. The second
  break has a real behavioral consequence: each group/partition now
  accumulates into its own downstream container as elements arrive, instead
  of being buffered as a list and replayed through `downstream` in a
  post-pass — invisible for a pure downstream, but a downstream with side
  effects (e.g. `to_map`'s duplicate-key `ValueError`) now observes them
  interleaved with the source. Both are logged in README's migration log.

  **The central design problem was dispatch-state lifetime, not the adapter
  shape.** A `Collector` is explicitly reusable across streams and
  compositions (`to_list` is a single shared module-level instance), so its
  accumulator is one fixed function — it cannot hold the
  `is_async`/`checked` classification flags a per-element user callable
  (a mapper, comparator, key function) needs, the way the old per-collection
  closures could. Every such factory's supplier now returns a small
  `__slots__` container carrying that state alongside the accumulation
  itself, so classification is created fresh per collection and never leaks
  across collections or across a `ParallelStream`'s racing branches. This
  keeps the per-element dispatch shape exactly as `add-callsite-dispatch`
  left it — no per-element method call was added on any user callable's
  hot path.

  `TerminalSink.begin()`/`end()` in `sink.py` now await what
  `_create_container()`/`_finish()` return (via the existing `_maybe_await`),
  so an async `Collector` supplier or finisher works without every sink
  needing its own override — every existing sink's plain return value passes
  through unchanged. `sink.py` also gained `Box` (`Counter` is now a `Box`
  subclass) as the general mutable-value container the scalar collectors'
  per-collection state boxes build on.

  Measured (interleaved reps, one process, 200k elements, matching the
  `collapse-collector-sink-duplication` benchmark protocol): `collect(to_list)`
  -37%, `collect(counting())` -39%, `collect(summing_int(...))` -18% —
  faster in every case, not just neutral, since `collect()`'s single-`Collector`
  path no longer goes through the generator bridge at all (it drives a
  terminal sink directly, like every other terminal operation). 477 tests
  pass (20 new, covering the `Collector` class itself, reuse-safety across
  sequential/concurrent/parallel collections, the unused-`combiner`
  guarantee, both rejection paths, and downstream-container isolation) at
  98% coverage. See `openspec/changes/redesign-collector-shape`.

- **Collapsed the duplicated bodies in `collector.py` and the repeated
  dispatch-state boilerplate in the sinks**, the four-part item that came out
  of the 2026-08-19 simplification read. All four parts landed, all
  behaviour-neutral, no public API change and no README edit. 457 tests pass
  unchanged at 98% coverage; `tests/` was not touched at all.

  **(a) The six summing/averaging bodies became two private factories.**
  `_summing(mapper, seed, coerce)` and `_averaging(mapper)`; the six public
  names survive as one-line wrappers, each keeping its own return annotation,
  which is where the Java-primitive distinction is actually expressed. The
  `collector.py` comment defending them was reworded: it defends six *names*,
  and had been read as defending six *bodies*. `coerce` is `None` rather than
  an identity callable on the int/long path, so no call is added per element
  and a mapper returning `Decimal`/`Fraction` still sums in its own type.

  **The design's hoisting decision was reversed mid-implementation, and this
  is the interesting part.** design.md required the `coerce is None` test to be
  hoisted out of the `async for`, which means writing the loop twice. Measured
  (interleaved, 41 reps, 200k elements) that was right on its own terms: the
  hoisted form matches the pre-change code and the single-loop form costs a
  reproducible ~2% on `summing_int`/`summing_long`. But `ruff` then fails with
  `C901 _summing is too complex (11 > 10)` — the duplicated loop trips the
  project's own mccabe gate, which the design had not accounted for.
  Suppressing that gate on a function whose complexity comes *entirely from
  duplication*, inside a change whose purpose is removing duplication, was the
  wrong trade. Shipped as one loop with a per-element `coerce is None` test:
  a branch, not a call, and ~2% against the +32-75% that got
  `add-callsite-dispatch` rejected.

  **(b) Eight sinks lost their hand-copied dispatch triple** to an
  `AsyncDispatch` mixin in `callable_dispatch.py` — the module already named
  for the concept, and already holding the canonical-shape comment the mixin
  now makes checkable. `_FilterSink`/`_MapSink`/`_PeekSink` and
  `_ForEachSink`/`_ReduceSink`/`_MinMaxSink`/`_MutableReductionSink`/
  `_MatchSink` mix it in and call `_init_dispatch(fn)` from `__init__`. It is
  a plain method, not an `__init__`, so it stays out of the MRO: those eight
  sit on two different bases with different constructor signatures. The stored
  callable unified on `self._fn`, replacing five different names
  (`_predicate`, `_mapper`, `_consumer`, `_accumulator`, `_comparator`);
  constructor parameters keep their descriptive names and annotations.
  `_SortedSink` keeps its own `_comparator` — it never had the triple.
  `_MatchSink` keeps its own `_cancelled`, which is short-circuit state, not
  dispatch state. **Verified mechanically** that all eight `accept()` bodies
  are identical to their pre-change form modulo that one rename, by AST-
  extracting each and diffing against `git show HEAD:` with the rename applied
  — so nothing was added to the per-element path, which is the whole reason
  this part was allowed where `CallSite` was not.

  **(c) `grouping_by`/`partitioning_by` now share `_group_into()`.** The
  design said `partitioning_by` would pass a `key_fn` wrapping its predicate
  in `bool(...)`. **That is unimplementable and the suite catches it:**
  dispatch classifies `key_fn` and awaits its *result*, so a sync `bool()`
  wrapper sees an unawaited coroutine for an async predicate — always truthy —
  and sorts every element into the `True` bucket
  (`tests/test_partitioning_by.py:37`). Shipped instead with a separate
  optional `coerce_key` applied to the awaited key. Not hoisted, unlike (a):
  this loop body already does a `setdefault` and an `append`, and hoisting
  would duplicate the only code the part extracts. The `downstream`
  comprehension deliberately stays at both call sites — it is the line the
  `Collector` redesign rewrites.

  **(d) `StatefulOp` now subclasses `StatelessOp`**, overriding `link()` alone.
  Gated on a grep first: the only `isinstance` touching these names
  (`tests/test_op_protocol.py:84`) tests concrete subclasses, not the two
  bases, so the part was safe to do. Both docstrings kept, plus a note that
  the subclassing is mechanical convenience and that the docstrings, not the
  hierarchy, carry the shared-state distinction.

  **Came in well under estimate: -69 code lines** (excluding comments and
  docstrings), or -79 coverage-measured statements, against the ~150
  estimated. The estimate counted the raw span of the deleted bodies including
  their blank and comment lines, and this change adds explanatory comments the
  old copies did not carry. See
  `openspec/changes/collapse-collector-sink-duplication`.

- **Landed the small-cleanups batch**, the ten-entry residue left by the
  Sink-chain redesign and its four follow-up changes. Nine entries were
  behaviour-neutral; one was a real defect.

  **The one behaviour change: a chain cancelled before its first element no
  longer pulls one.** `BaseStream._drive()` and `_drive_to_sequential()`
  queried `cancellation_requested()` only *after* an `accept()`, so a chain
  already cancelled at `begin()` consumed one source element and ran every
  upstream op's side effects on it. Both loops now check once after `begin()`
  and skip the `async for` entirely; `end()` stays outside the guard, so the
  lifecycle still completes. `ParallelStream._drive_to()` got the same guard.

  **The roadmap's framing of this item was wrong and is corrected here.** It
  said "a satisfied `limit()` still pulls one extra element from the source".
  It did not: `_LimitSink` sets `_cancelled` inside the `accept()` that fills
  the last slot, so the existing post-`accept()` check already broke without an
  extra pull. The only reachable over-pull was the *pre-settled* case —
  `limit(0)`, or any op cancelled before the first element. Verified before
  starting: `Stream.of([1,2,3]).peek(seen.append).limit(0).to_array()` returned
  `[]` but left `seen == [1]`.

  **The fix needed a second half not in the original write-up.** The loop guard
  alone does nothing, because `_LimitSink._cancelled` was only ever set inside
  `accept()` — a `limit(0)` sink reported `False` right after `begin()`. Added
  `_LimitSink.begin()`, which calls `super().begin()` (that is what resolves
  `self._state`) and then settles `self._cancelled = self._state.value >=
  self._max_size`. Once per composition, not per element. `accept()` was left
  byte-identical, since a shared counter can still fill between one sink's
  `begin()` and its next `accept()`.

  **The nine neutral entries.** `BaseStream._sequential()` — which did no
  sequential execution and never touched `self` — became a module-level
  `_wrap_sink()`, after Java's `AbstractPipeline.wrapSink()`, which is exactly
  this operation; the old name sat three lines from `_drive_to_sequential()`,
  which *does* mean the execution mode. `_compose()`'s `self._chain[:]` and
  `_parallel()`'s per-branch `intermediaries[:]` were dropped (nothing mutates
  the chain, and `_derive()` already copies on extend). `GeneratorBridgeSink`
  now exposes a plain `buffer` attribute the driving loop clears in place,
  replacing a `drain()` that allocated a fresh list once per element on the
  generator path — a plain attribute, not a `@property`, since the loop reads
  it twice per element and a descriptor call would give back most of what the
  removed allocation buys. `to_generator()` dropped its hand-rolled
  `hasattr(composition, "aclose")` branch for the existing `_maybe_aclosing`
  (no import cycle: `base_stream.py` never imports `collector`, and
  `parallel_stream.py` already imported it from there). `sequential()`/
  `parallel()`, identical but for the class they construct, were factored onto
  `_handoff(cls)`, each keeping its own local import so a `sequential()` call
  does not import `parallel_stream`. `Stream.__init__` and
  `ParallelStream.__init__`, both pure `super().__init__` pass-throughs, were
  deleted, as was `to_array()`'s duplicate `_check_not_consumed()`. And
  `Accumulator` (`type.py`) was widened to
  `Callable[[T, T | R], T | R | Awaitable[T | R]]` — `_ReduceSink.accept()`
  awaits it and the suite already covered async accumulators, but
  `fix-type-py-callable-alias-defects` had scoped the terminal aliases out.

  No public API change and no README edit: every name touched is private except
  `Accumulator`, whose widening is additive to its union and whose README row
  names only the alias. All 448 pre-existing tests pass, with three mechanical
  edits: `tests/test_sequential.py` calls the module-level `_wrap_sink()`
  instead of reaching for it through an instance, and `tests/test_sink.py` and
  `tests/test_op_protocol.py` assert on `bridge.buffer` where they had asserted
  on `bridge.drain()`. 457 tests pass at 99% coverage — 9 new, covering
  `limit(0)` on `Stream` and `ParallelStream`, that no source pull happens, the
  full `begin()`/`end()` lifecycle on a chain that pulled nothing, the
  protocol-level cancelled-at-`begin()` case against both the test double and
  the real driving loop, and the bridge's in-place clear and buffer identity.
  `sink-protocol` gained the pre-first-pull requirement; `pipeline-composition`
  gained the `limit(0)` guarantee and the no-defensive-copy invariant; the
  `_sequential()` references in `pipeline-composition` and `stream-iterator`
  were re-pointed. See `openspec/changes/batch-small-cleanups`.

- **Converted the terminal operations to real `TerminalSink`s**, closing the
  half-conversion the Sink-chain redesign explicitly scoped out. `BaseStream`
  gained `_drive_to(terminal)` — link the chain onto a terminal sink, push
  source → head → terminal, return `terminal.result()` — and
  `_drive_to_sequential(terminal)`, the never-overridden ordered form. The pair
  mirrors the existing `_compose()`/`_drive()` split: `_drive_to()` dispatches
  (`ParallelStream` overrides it), `_drive_to_sequential()` stays ordered on
  either subclass. A new `src/snakestream/terminals.py` (206 lines) holds seven
  terminal sinks — `_CountSink`, `_ForEachSink`, `_ReduceSink`, `_MinMaxSink`,
  `_MutableReductionSink`, `_FindSink`, `_MatchSink` — plus `_UNSET`, which
  moved out of `stream.py` since a sink cannot import it back. Every terminal
  method in `stream.py` is now one or two lines; `stream.py` went from 215
  statements to 111.

  `_drive()`/`GeneratorBridgeSink` were kept for exactly what needs a
  generator, as scoped: `iterator()`, `collect(collector)` (so `to_array()` and
  every collector are untouched), `_concat`, the `sequential()`/`parallel()`
  handoff, and `flat_map`'s inner-stream composition. No terminal reaches the
  bridge any more, and the `TerminalSink` seat now has six real occupants that
  use `_create_container`/`_finish`/`result()` as intended rather than
  overriding them — which is the template the **Next**-bucket `Collector`
  redesign needed, and which it is now **unblocked** by.

  **Two behavior changes, both intended, neither breaking.** (a) Short-circuiting
  terminals now report `cancellation_requested()`, so a settled `any_match` /
  `all_match` / `none_match` / `find_first` / `find_any` stops the whole chain
  instead of abandoning a generator: `.peek(fn).any_match(p)` calls `fn` once,
  not once per element, and `.flat_map(m).find_first()` takes one element from
  the first inner stream and closes it rather than draining it. A user relying
  on a side-effecting `peek()` or mapper firing past the short-circuit point
  would see the difference — it is the same class of fix `limit()` got, so it is
  a behavior note rather than a **BREAKING** migration-log entry; no signature
  or return value changed. (b) `ParallelStream` terminals gained cancellation at
  the outer loop only.

  **`ParallelStream` drives the terminal over the racing generator** rather than
  sharing one terminal sink across the branches: `_drive_to()` is overridden to
  push `_compose()`'s output into the single terminal. Parallel semantics are
  therefore identical to before and the bridge's cost stays on that path — the
  measured win is sequential-only. Sharing a terminal across branches was
  rejected: it would make `begin()`/`end()` refcounted, the accumulator
  concurrently mutated, and would need `_ReduceSink`/`_MinMaxSink` to define a
  merge across partitions, which is exactly the `combiner` work parked in
  **Later** behind real partitioned execution. Consequence, accepted: an
  in-flight branch's own `_LimitSink`/`_FlatMapSink` never sees a terminal's
  cancellation, since the terminal is not in that branch's chain. `_parallel()`'s
  existing `finally:` already cancels and gathers the pending tasks, so teardown
  is clean — a missed optimization, not a correctness gap.

  **One defect found by the new tests, and one fix beyond the planned scope.**
  `_FindSink.accept()` initially overwrote its container on every element, which
  is correct only if nothing pushes after cancellation — but `_SortedSink.end()`
  flushes its entire buffer downstream in one go with no driving loop in
  between, so `.sorted().find_first()` returned the *last* element. Fixed by
  guarding both short-circuiting sinks to ignore anything pushed after they
  settle. That exposed the real gap one level up: `_SortedSink.end()` did not
  check `cancellation_requested()` while flushing, so `peek()` still fired for
  every element after the answer was known. Added that check between pushes
  (`ops.py`), mirroring `_FlatMapSink`'s existing inner-loop check — two lines,
  outside the change's planned task list, but without it the change's headline
  benefit has a hole for any chain containing `sorted()`. The terminal-side
  guards were kept rather than resting on that invariant and are pinned by
  direct sink-level tests.

  **Benchmark (2026-08-19, same harness: Python 3.14.5, 20,000 elements, chain
  of 8 `.map()` ops, best of 5, three interleaved rounds per condition via
  `git stash`; best round per condition shown, round 1 was a cold outlier for
  both):**

  | Scenario | Before | After | Δ |
  |---|---|---|---|
  | `collect(to_list)` — unchanged generator path, control | 1974.3 | 2004.7 | ~flat |
  | `count()` | 1938.5 | 1644.3 | **−15.2%** |
  | `for_each()` | 1982.4 | 1622.9 | **−18.1%** |
  | `reduce()` | 1994.1 | 1671.6 | **−16.2%** |

  The flat control on the generator path is what rules out machine drift: only
  the paths that stopped round-tripping through the bridge moved. This recovers
  a good part of what the redesign measured and gave back to the buffer-and-yield
  step, as that item predicted.

  No public API change — every name added is private and unexported, so README
  needed no parity-table or migration-log edit. All 421 pre-existing tests pass
  **unmodified**, which was the primary regression signal; 27 new tests were
  added (`tests/test_terminal_sinks.py`, plus two protocol-level cases in
  `tests/test_sink.py`) covering `reduce()`'s reseeding edge cases, terminal
  cancellation reaching `peek`/`limit`/`flat_map`, the ordered drive on a
  `ParallelStream`, parallel terminals, and the two short-circuit guards. 448
  tests pass at 99% coverage (98.63% branch), `terminals.py` at 100%. New
  `terminal-sinks` spec; `sink-protocol` and `pipeline-composition` extended for
  terminal-originated cancellation. See
  `openspec/changes/convert-terminals-to-sinks`.

- **Split the op/sink definitions out of `stream.py` into `ops.py`.** The eight
  op/sink pairs (`_FilterSink`/`_FilterOp` through `_SkipSink`/`_SkipOp`) moved
  verbatim into a new `src/snakestream/ops.py`, leaving `stream.py` as the public
  `Stream` API plus `PROCESSES`, `_UNSET` and `_concat`. `stream.py` went from
  485 to 312 lines; `ops.py` is 199. The class bodies are byte-identical to what
  they were in `stream.py` — verified by diffing the moved block against the
  original lines before deleting them — so the whole change is the cut, the new
  module's import header, and one import line in `stream.py`.

  Sinks moved with their ops rather than staying behind: after the op-collapse
  change each op is a two-to-four-line `_sink_cls = <its sink>` declaration, so
  the pair is only readable together. The ops were not folded into `sink.py`
  either — that file is the protocol (`Sink`, `Op`, `IntermediateSink`,
  `TerminalSink`, `StatelessOp`/`StatefulOp`, `GeneratorBridgeSink`), and mixing
  the concrete ops into it would re-create the same two-concerns-in-one-file
  problem one module over.

  No import cycle: `ops.py` imports from `sink.py`, `sort.py`,
  `callable_dispatch.py` and `type.py` only. `_FlatMapSink` is the one op that
  touches a `Stream`, and it does so purely by duck typing
  (`self._flat_mapper(element)._compose()`); its `FlatMapper` annotation resolves
  through `type.py`'s existing `TYPE_CHECKING` guard, so no guard was needed in
  `ops.py`. `stream.py` shed `aclosing`, `merge_sort` and all seven `sink.py`
  imports in the cut, keeping `check_comparator_result_type`, `is_async_callable`
  and `isawaitable`, which the `Stream` API still uses.

  Behavior-neutral, and no spec or README edit was needed: every moved name is
  private and unexported, so no public API surface changed and neither
  `sink-protocol` nor `pipeline-composition` describes which module the concrete
  ops live in (they describe the protocol classes in `sink.py`). The change
  therefore declared `skip_specs: true` and shipped no spec delta. The only test
  edit was `tests/test_op_protocol.py`'s import of the eight op classes moving to
  `snakestream.ops`; `tests/test_sequential.py` and `tests/test_sink.py` define
  their doubles against `sink.py` and needed no change. 421 tests pass at 99%
  coverage — identical to the pre-change run, with `ops.py` at 100%. The **Small
  cleanups** item's `stream.py` line references were re-pointed to their new
  lines. See
  `openspec/changes/archive/2026-08-19-split-ops-into-ops-module`.

- **Collapsed the eight op classes onto shared bases.** `sink.py` gained
  `StatelessOp` and `StatefulOp` — both storing the arguments the op was
  constructed with and forwarding them to a class-level `_sink_cls`, the
  stateful one also passing `self` so its sink can key the state map — plus a
  `StatefulSink` base and a `Counter` value type. All eight ops are now
  declarations: five are two lines (`class _MapOp(StatelessOp): _sink_cls =
  _MapSink`), three add a one-line `make_shared_state()`. `stream.py` went from
  537 to 485 lines and `_DistinctSink`/`_LimitSink`/`_SkipSink` lost their
  hand-written `begin()` overrides.

  The state-map lookup written out at three sites became one `state_map.get()`
  in `StatefulSink.begin()`, and its fallback now comes from the op's own
  `make_shared_state()` rather than a literal retyped in the sink — so an op's
  state shape is stated exactly once and shared and local state cannot drift.
  That guarantee was added to the `sink-protocol` spec as a new scenario under
  **Shared state is delivered through begin**, the change's only spec delta.
  `_LimitSink._count: list[int]` and `_SkipSink._skipped: list[int]` became a
  `Counter` with a `value` attribute, so the reserve-before-await race block
  now reads `self._state.value >= self._max_size`.

  Naming follows Java's `StatelessOp`/`StatefulOp`, with the class docstrings
  pinning that the axis here is *shared* state — state crossing
  `ParallelStream`'s branches — not local buffering, which is why the
  whole-stream-buffering `_SortedOp` is a `StatelessOp`.

  Behavior-neutral and no public API change; every name touched is private or
  unexported, so README needed no edit. `parallel_stream.py` needed no edit
  either — it already called `make_shared_state()` unconditionally and keyed
  only non-`None` results. 421 tests pass at 99% coverage (six new: the
  factory-sourced fallback, `Counter` independence, shared-counter increment
  across two sinks from one op, and argument forwarding through both bases).
  Two existing tests were touched: `test_op_protocol.py`'s fresh-container
  assertion asserted emptiness as `first in ([0], set())`, which named the old
  list representation, and two test-local doubles (`_StatelessOp`,
  `_StatefulOp`/`_StatefulSink`) were renamed to `_LinkOnlyOp` and
  `_TallyingOp`/`_TallyingSink` since their names now collide with the real
  protocol classes. The doubles still subclass `Op`/`IntermediateSink`
  directly, deliberately: their job is to pin the protocol, not the
  convenience bases.

  **Benchmark (2026-08-19, same harness: Python 3.14.5, 20,000 elements, best
  of 5, interleaved before/after rounds to control for machine drift):** 8×
  `.map()` 1935–2026 ns/element before, 2001–2071 after; `.skip(1).limit(n)`
  1081–1120 before, 1037–1145 after. Run-to-run spread within either condition
  (±5–8% on this WSL2 box) exceeds the gap between them, and the 8× `.map()`
  path's per-element code is byte-identical across the change — everything the
  change touches per element is the `Counter` attribute load replacing a list
  index, and everything else (`link()`, `begin()`) runs once per composition.
  No measurable regression.

  **Unblocks** the `ops.py` split still in **Now**, which is now a pure move.
  See `openspec/changes/collapse-op-classes`.

- **Introduced an `Op` ABC** (`sink.py`) and typed the chain against it,
  completing the op/sink protocol the Sink-chain redesign left half-specified.
  `Op` has one abstract member, `link(downstream) -> Sink`, and one concrete
  `make_shared_state() -> Any` returning `None`; all eight shipped ops
  (`_FilterOp`, `_MapOp`, `_PeekOp`, `_SortedOp`, `_FlatMapOp`, `_DistinctOp`,
  `_LimitOp`, `_SkipOp`) now subclass it, the three stateful ones keeping their
  `make_shared_state()` overrides unchanged.

  `_chain`, `_derive`, `_sequential`, `_drive` and `ParallelStream._parallel`
  are typed `list[Op]` instead of `list[Any]`, so `ty` — gated in CI on the
  3.14 leg — can now see the pipeline's central data structure. The
  `getattr(op, "make_shared_state", None)` sniff in `parallel_stream.py` is
  gone, replaced by an unconditional call keying the state map only on a
  non-`None` result; `None` is now a specified contract meaning "no shared
  state", so a stateful op returns a container and never `None`.

  Behavior-neutral by construction: no method body was edited and no public API
  changed (`Op` is not exported, and all eight op classes stay private), so
  README's parity tables need no edit. 415 tests pass at 98.58% coverage. The
  existing op test doubles in `tests/test_sink.py` and `tests/test_sequential.py`
  were made to subclass `Op` so they stay faithful to the protocol. See
  `openspec/changes/archive/2026-08-19-introduce-op-abc`.

  **Unblocks** the op-class-collapse item still in **Now** — the shared
  `*args`/`_sink_cls` base that item wants now has a typed base class to hang
  off, and the `StatefulSink` base it also wants can rely on every op having a
  `make_shared_state()` to key against.

- **Investigated and rejected** replacing `callable_dispatch.py`'s hand-copied
  async-dispatch pattern with a `CallSite` object. The pattern is genuinely
  duplicated — `callable_dispatch.py` documents a 6-line shape as a 40-line
  comment and 24 per-element sites across `stream.py`, `collector.py` and
  `sort.py` retype it by hand, with `_classify_step` existing only to relieve
  mccabe pressure in `to_map`/`reducing` and `sort.py` carrying the same state
  as a positionally-indexed `state = [is_async, checked]` list. The proposal
  was to wrap each callable in a small object owning that state.

  Killed on measurement, at the benchmark gate the change's own tasks placed
  after converting a single site. Harness matched the one
  `optimize-callable-dispatch` and `redesign-pipeline-sink-chain` used (Python
  3.14.5, 20,000 elements, chain of 8 `.map()` ops, best of 5, three runs per
  variant); only `_MapSink` was converted, so with 8 `.map()` ops the figures
  isolate per-site, per-element cost:

  | Variant | ns/element | vs baseline |
  |---|---|---|
  | Baseline (inline shape, as shipped) | 1907, 1992, 2162 | — |
  | Floor (dispatch logic deleted; sync-only, incorrect) | 1826, 1878, 1998 | ~0% |
  | `CallSite.call()` sync, caller branches on `.is_async` | 2529, 2589, 2840 | **+32%** |
  | `CallSite` with `async def __call__` | 3399, 3444, 3468 | **+75%** |

  The decisive figure is the floor: deleting the dispatch logic outright buys
  nothing measurable over the baseline, so the inline five-branch shape costs
  approximately zero — two attribute loads and two branches the CPU predicts
  correctly after the first element, with no Python-level call and no
  allocation. The comparison is therefore not "abstraction vs. cheaper
  abstraction" but "abstraction vs. free", and both variants pay a
  Python-level call per element per site that the inline code does not (~180
  ns/site/element for the coroutine frame, ~70 ns for the bound-method call
  alone). The design's stated fallback — a two-shape `CallSite` picking a sync
  fast path in `__init__` — does not help, since the fast path still has to be
  reached through the call that is itself the cost. `optimize-callable-dispatch`
  bought 2.6x by hoisting exactly these branches out of the per-element path;
  the two variants give back roughly half and roughly a fifth of that.

  **Consequence:** the duplication is now a deliberately-accepted cost with
  numbers behind it rather than an open cleanup item, and should not be
  re-proposed without new evidence. Anyone adding a 25th dispatch site should
  still copy the canonical-shape comment in `callable_dispatch.py` — that
  comment is load-bearing, not a smell to be refactored away. No code changed;
  the working tree was reverted to HEAD and the full suite (394 tests) passes
  unmodified. See
  `openspec/changes/archive/2026-08-18-add-callsite-dispatch` for the proposal,
  design, and `benchmark-findings.md`.

  **One residual finding was salvaged and acted on.** The investigation
  established that per-callable classification independence — `to_map`'s
  key/value/merge functions and `reducing`'s mapper/binary operator each
  classifying on their own, so any mixture of sync and async among them works
  — was real behavior with **no test coverage**: `tests/test_to_map.py` and
  `tests/test_reducing.py` each covered all-sync and all-async but never a
  mixed pair. Closed by adding the five mixed-mode tests (sync key + async
  value, async key + sync value, sync mappers + async merge on a colliding
  key, sync mapper + async operator, async mapper + sync operator) and
  promoting the rejected change's drafted delta into the `callable-dispatch`
  spec as a new **Classification state is per callable** requirement. All five
  passed on first run — the behavior was already correct, so this is coverage
  and documentation of existing behavior, not a fix. Written directly to
  `openspec/specs/callable-dispatch/spec.md` rather than through a change of
  its own, since the requirement text already existed in the rejected
  change and would otherwise have been archived away unapplied.
- Redesigned pipeline execution from nested async-generator delegation to a
  push-based `Sink` protocol (`begin(state_map)`/`accept(element)`/`end()`/
  `cancellation_requested()`), replacing the closures-in-`_chain` model. New
  `src/snakestream/sink.py` defines the protocol plus `IntermediateSink` (a
  `downstream`-holding base that propagates `begin()`/`end()` and forwards
  `cancellation_requested()`) and `TerminalSink` (creates its container in
  `begin()`, accumulates in `accept()`, exposes the finished value via
  `result()`) — the terminal seat a future `Collector` redesign can plug
  into directly. `GeneratorBridgeSink` occupies that seat to let
  `BaseStream._compose()` keep returning a plain `AsyncGenerator`: pushing
  stays entirely internal to the chain, with a buffer-and-drain driving loop
  (`BaseStream._drive()`) converting pushes back into yields, so all 11
  terminal ops, every collector, `iterator()`, and `_concat` needed no
  changes. All eight intermediate ops (`filter`, `map`, `flat_map`, `sorted`,
  `peek`, `distinct`, `limit`, `skip`) are now op/sink pairs in `stream.py`
  (`_FilterOp`/`_FilterSink`, etc.) — the op is a stateless, reusable
  descriptor exposing `link(downstream) -> Sink` (and, for stateful ops, a
  `make_shared_state()` factory), while the sink is built fresh per
  composition and holds the actual per-composition state.
  `make_state()`/`state_map` `getattr`-introspection is gone:
  `ParallelStream._parallel()` now calls each op's `make_shared_state()`
  directly to build one shared state map, passed into every racing branch's
  `begin()`. `limit()`'s short-circuit moved from the op reaching up to
  `aclose()` its own upstream to `cancellation_requested()` propagating to
  the driving loop, which now owns closing the source (via a
  `_maybe_aclosing()` helper tolerant of sources with no `aclose()`, needed
  since `_drive()` — unlike the old bare-`_stream`-passthrough on an empty
  chain — always wraps the source). `flat_map()` drops its
  `collect(to_generator)` wrapper layer, iterating the inner stream's own
  `._compose()` directly while keeping `aclosing()` around it, and checks
  `downstream.cancellation_requested()` between pushed elements so a
  downstream `.limit()` still stops it mid-inner-iteration instead of
  over-pushing.

  **Two scoping decisions taken (from `design.md`):** (a) push stays
  internal only — `_compose()` still returns an `AsyncGenerator`, avoiding
  the pull-bridge (`Spliterator`) that pushing all the way to the terminal
  would need; (b) the terminal seat ships now, with one implementation
  (`GeneratorBridgeSink`), rather than deferring it to the Collector
  redesign.

  **Benchmark (2026-08-18, this repo's dev environment, Python 3.14.5,
  20,000 elements, chain of 8 `.map()` ops, best of 5):** 2,480.6 ns/element
  before, 1,872.6 ns/element after — a ~24.5% gain, consistent with (and
  better than) the proposal's 15–17% estimate; the bridge's buffer-and-yield
  step gives back some but not all of the fully-pushed-to-terminal figure
  the proposal separately measured.

  The entire pre-existing test suite passed unmodified except one
  internals-facing test (`test_sequential_long_chain_does_not_recurse_at_
  build_time`) updated to construct fake ops with `.link()` instead of raw
  closures, since `_sequential()`'s signature is now `(intermediaries,
  terminal_sink) -> Sink` rather than `(intermediaries, iterable) ->
  AsyncGenerator` — an intentional, documented signature change, not a
  behavior regression. Added `tests/test_sink.py` covering the
  `sink-protocol` spec directly (lifecycle ordering, empty source, zero/one/
  many pushes per accept, pushing from `end()`, state-map lookup/fallback/
  sharing, cancellation propagation, terminal `result()`). Added a direct
  `to_generator()`-with-no-`aclose()`-source test (`tests/test_collect.py`)
  to keep that branch covered, since `_compose()` no longer ever returns a
  bare source without `aclose()` the way the old empty-chain passthrough
  did. New `sink-protocol` spec; `pipeline-composition` updated to describe
  state and cancellation via `begin(state_map)`/`cancellation_requested()`
  instead of the old `make_state()`/`state_map` convention and `limit()`'s
  self-closing upstream. No public API change; `collector.py` untouched.
  See `openspec/changes/redesign-pipeline-sink-chain`.
- Added `sorted()`'s row to README's Stream API table. `sorted()` had been
  implemented since before this roadmap existed (`stream.py:191`) but was
  never given a row in the table; the migration log referenced it three
  times, which is what made the omission easy to miss. Doc-only, no code
  change.
- Specialized `callable_dispatch.py`'s dispatch from per-result to
  per-callable: `is_async_callable(fn)` classifies a callable once
  (recognizing a plain `async def` function and a callable object whose
  `__call__` is `async def`), and the 26 per-element call sites across
  `stream.py`, `collector.py` and `sort.py` hoist an `is_async` flag out of
  their loop instead of calling `inspect.isawaitable` on every result.
  A first-invocation `isawaitable` check is kept as a safety net so a
  sync-signatured callable that returns a coroutine (the defect
  `add-maybe-await-helper` fixed) is still handled correctly. `_maybe_await`
  is retained for the handful of call sites invoked once per composition
  (e.g. `collect()`'s `supplier`), where specialization buys nothing.
  Measured in this repo's dev environment (Python 3.14.5, 20,000 elements,
  a chain of 8 `.map()` ops, best of 5 runs): 5,949 ns/element before,
  2,247 ns/element after — a 2.6x speedup, in line with the throwaway
  benchmark harness's 5,775 → 2,064 ns/element (2.8x) recorded in
  `design.md`. Carries one deliberate contract narrowing, tracked as
  **BREAKING** in README's migration log: a callable invoked once per
  element must be consistently sync or consistently async — one that
  returns an awaitable for some elements and a plain value for others is no
  longer supported (it has no Java analogue). See
  `openspec/changes/optimize-callable-dispatch`.
- Decided and implemented the mutable-builder vs. immutable-pipeline
  question (the former top **Next**-bucket item, previously "Decide
  mutable-builder vs. immutable-pipeline semantics"). Explored three
  positions during a design session: (A) keep mutate-and-return-self and
  just document the aliasing risk; (B) copy-on-write with the old
  reference left silently usable (superficially "forkable," but still a
  footgun since the underlying `self._stream` is single-pass, so both
  forks would race it exactly like `ParallelStream` branches do); (C)
  Java-exact — new instance plus invalidating the old reference on reuse.
  Landed on a scoped version of (C): every intermediate op (`map`,
  `filter`, `flat_map`, `sorted`, `distinct`, `peek`, `limit`, `skip`) and
  both mode switches (`sequential()`, `parallel()`) now return a **new**
  `Stream`/`ParallelStream` instance via a new `BaseStream._derive()`
  helper (`base_stream.py`) instead of mutating and returning `self`;
  using an already-superseded old reference for any further
  pipeline-building or terminal call now raises a new
  `IllegalStateException` (`exception.py`), checked via a
  `self._consumed` flag set only by the ops that build a new instance.
  Deliberately did **not** go full Java-exact: terminal ops
  (`collect`, `reduce`, `for_each`, etc.) check `self._consumed` but never
  set it, so repeating a terminal op on a reference that was never used to
  build a further instance keeps today's exact behavior (an exhausted
  source yields an empty result rather than raising) — reversing that
  would have undone the already-shipped, tested `fix-stream-rerun-state`
  contract that `pipeline-composition` documents, which was judged a
  separate, already-settled decision this change shouldn't revisit.
  `on_close()`/`close()` were kept completely exempt from the new check,
  matching how Java itself tracks close handlers at the pipeline's source
  stage rather than per operation, independent of any per-op immutability
  question. Discovered during implementation: `BaseStream.__init__`'s
  `self._close_handlers = close_handlers or []` treated an *empty* list as
  falsy and silently created a new list instead of keeping the passed-in
  reference — invisible before since intermediate ops never re-invoked the
  constructor, but every op does now via `_derive()`, breaking
  close-handler continuity across the very first op called before any
  `on_close()`. Fixed to `[] if close_handlers is None else close_handlers`.
  Added `tests/test_pipeline_immutability.py`: new-instance-per-op checks
  and invalidation-raises checks for all 8 intermediate ops, invalidation
  checks across all terminal ops and both mode switches, derived-instance
  usability, the unextended-reference non-regression case, and the
  `on_close()`/`close()` exemption. Added a new `pipeline-immutability`
  spec. Updated README's migration log (**BREAKING**). See
  `openspec/changes/make-stream-ops-immutable`.
- Implemented `Stream.find_first()` (`stream.py`), matching Java's
  `Stream.findFirst()`. The previous body was a dead
  docstring-commented-out stub — a string literal, never executed — with a
  comment claiming it was blocked on "ordered parallel stream." That
  blocker didn't actually apply to `Stream`: `Stream._compose()` is already
  sequential, so `find_first()` there is identical in body to `find_any()`.
  The real gap was narrower and `ParallelStream`-specific:
  `ParallelStream._compose()` races `PROCESSES` branches via
  `asyncio.wait(..., FIRST_COMPLETED)`, so first-*arrival* isn't
  first-*encounter-order*. Fixed by adding a `ParallelStream.find_first()`
  override that checks `self.is_ordered()`: when ordered (the default),
  pulls via `self._sequential(self._chain[:], self._stream)` — the same
  building block `for_each_ordered()` uses — for a strictly ordered,
  single-flight pull through the chain, guaranteeing the true first element
  in encounter order at the cost of `.parallel()`'s concurrency for this
  one terminal call (the same trade-off Java's own `forEachOrdered()`/
  ordered `findFirst()` make); when the stream has been marked
  `unordered()`, delegates to `find_any()`'s existing racing behavior,
  matching Java's documented relaxation of `findFirst()`'s encounter-order
  guarantee for unordered streams. This is the first consumer of the
  `is_ordered()`/`unordered()` flag added by `add-stream-unordered`. Added
  `tests/test_find_first.py`: non-empty/empty `Stream`,
  first-element-only pulled, and — mirroring `test_for_each_ordered.py`'s
  jumbled-source-with-positional-delay pattern — ordered-`ParallelStream`
  coverage proving `find_first()` returns the true first element rather
  than the first to arrive, plus unordered-`ParallelStream` coverage
  showing it races without waiting for a full ordered pull. Updated
  README's parity table (`find_first()` row, previously "Not implemented
  yet"). No breaking changes. See
  `openspec/changes/add-stream-find-first`.
- Fixed three resource/lifecycle defects found in review: (a) `flat_map()`
  (`stream.py`) leaked the current inner stream's async generator when the
  outer chain short-circuited (e.g. a downstream `.limit()`) — each outer
  element's fresh `flat_mapper(i).collect(to_generator)` generator was only
  ever exhausted, never explicitly `.aclose()`'d, so an early `GeneratorExit`
  on the outer chain abandoned whatever inner generator was mid-iteration.
  Fixed by wrapping that inner generator in `contextlib.aclosing()`
  (`stream.py`). Discovered during implementation: `aclosing()` alone wasn't
  sufficient — `collect(to_generator)` returns a second-layer wrapper
  generator (`collector.py`'s `to_generator()`) whose `async for n in
  composition: yield n` body didn't propagate `.aclose()` to `composition`
  either, confirmed with a minimal repro showing a plain `async for` never
  auto-closes what it iterates. Fixed `to_generator()` to also wrap
  `composition` in `aclosing()`, guarded by `hasattr(composition, "aclose")`
  since `to_generator()` also accepts plain `AsyncIterable`/`AsyncIterator`
  objects without an `aclose` method (e.g. a custom `__anext__`-only
  iterator, already covered by `tests/test_of.py::test_input_async_iterator`).
  This closes the gap only as deep as `flat_map()`'s stated repro case (a
  single-level inner stream); N-layers-deep propagation across every op in
  `stream.py` remains out of scope, tracked under the **Next**-bucket
  Sink-chain redesign item. (b) `BaseStream.close()` (`base_stream.py`)
  iterated `_close_handlers` with a plain `for` loop and no `try`/`except`,
  so a raising handler stopped every handler after it from running, unlike
  Java's try-with-resources convention of running every closer regardless.
  Fixed by calling every handler inside a per-handler `try`/`except
  Exception`, collecting failures, then raising the first captured exception
  once every handler has run (not an `ExceptionGroup`, since this project's
  CI matrix still targets Python 3.10). (c) `StreamBuilder.build()`
  (`stream_builder.py`) passed `self._elements` into `Stream(...)` by
  reference rather than snapshotting it, so `add()`/`accept()` calls made
  *after* `build()` leaked into the already-built stream. Fixed by
  snapshotting via `list(self._elements)`. Added regression tests in
  `tests/test_close.py`, `tests/test_flat_map.py`, and a new
  `tests/test_stream_builder.py`. Added a new `stream-builder` spec
  capturing `StreamBuilder`'s previously-undocumented `add()`/`accept()`/
  `build()` contract, and extended `stream-close-handling` and
  `pipeline-composition` for the `close()`/`flat_map()` fixes. Updated
  README's migration log: `StreamBuilder.build()`'s snapshot behavior is
  tracked as **BREAKING** per `CLAUDE.md`'s convention (relying on
  post-build mutation leaking into a built stream was never a documented
  feature). See `openspec/changes/fix-resource-lifecycle-defects`.
- Fixed three `type.py` callable-alias defects found in review: (a)
  `Mapper = Callable[[T], R | None]` now includes `Awaitable[R | None]`,
  matching `Predicate`/`Comparator`'s existing sync-or-async pattern and
  `map()`'s actual `_maybe_await`-based dispatch, which already supported
  async mappers without the type declaring it; (b) `Consumer` changed from
  `Callable[[T], T]` (wrong return type — a consumer's return value is
  discarded, not a `T`) to `Callable[[T], None | Awaitable[None]]`, and
  `for_each()`/`for_each_ordered()` (`stream.py`), which previously inlined
  their own `Callable[[T], Any]` instead of using the alias, now use
  `Consumer[T]`; (c) deleted `Filterer = Callable[[T], T]`, dead code never
  referenced anywhere in `src/` (`filter()` uses `Predicate`). Both alias
  widenings are additive to their unions, so no previously-valid sync usage
  is affected. Typing-only change, no runtime behavior differs. See
  `openspec/changes/fix-type-py-callable-alias-defects`.
- Added `groupingBy(classifier, [downstream])` / `partitioningBy(predicate,
  [downstream])`, implemented as `grouping_by`/`partitioning_by`
  (`collector.py`) — `collector.py`'s equivalent of `Collectors.groupingBy`/
  `partitioningBy`, closing out the roadmap's `Collectors`-parity effort.
  Both bucket elements first (`grouping_by` via a `classifier` mapper into a
  `dict[R, list[T]]`; `partitioning_by` via a `predicate` into a fixed
  `{True: [...], False: [...]}`, always populating both keys even when one
  partition is empty, matching Java's `Collectors.partitioningBy` exactly)
  then re-drives each bucket's elements through an optional `downstream`
  collector (default `to_list`) via a small `_generator_of(items)` helper
  that re-wraps the buffered list as a fresh `AsyncGenerator`, since
  downstream collectors are written to consume a composition, not a plain
  list — enabling `grouping_by(classifier, counting())`-style composition
  immediately, without downstream collectors needing to know they're being
  reused this way. `grouping_by`'s `classifier` and `partitioning_by`'s
  `predicate` reuse the same sync/async dispatch (`_maybe_await`) as every
  other collector. Added `tests/test_grouping_by.py`,
  `tests/test_partitioning_by.py`. Updated README's `Collectors` table with
  two new rows. No breaking changes. See
  `openspec/changes/archive/2026-08-18-add-collectors-groupingby-partitioningby`.
- Added `toMap(keyMapper, valueMapper, [mergeFunction])` / `toSet()`,
  implemented as `to_map`/`to_set` (`collector.py`) — structural collectors
  materializing into a `dict`/`set` instead of `to_list`'s `list`, matching
  `Collectors.toMap`/`Collectors.toSet`. `to_map` maps each element to a
  key/value pair via `key_mapper`/`value_mapper` (sync or async, dispatched
  through `_maybe_await`); a duplicate key raises `ValueError` unless a
  `merge_function` is given, in which case the collision resolves via
  `merge_function(existing, new)`, matching Java's
  `toMap(keyMapper, valueMapper, mergeFunction)` overload. `to_set()` takes
  no arguments and simply collects into a `set`, deduplicating via
  element `__hash__`/`__eq__` same as Java's `HashSet`-backed collector.
  Added `tests/test_to_map.py`, `tests/test_to_set.py`. Updated README's
  `Collectors` table with two new rows. No breaking changes. See
  `openspec/changes/archive/2026-08-18-add-collectors-tomap-toset`.
- Added `min_by(comparator)`, `max_by(comparator)`, and `reducing(...)`
  (`collector.py`) — collector wrappers around `Stream.min`/`max`/`reduce`'s
  already-implemented logic, exposed as `collect()`-compatible collectors
  rather than terminal-op methods, matching Java's `Collectors.minBy`/
  `maxBy`/`reducing` (adapted to this project's existing snake_case naming
  convention, e.g. `for_each`/`to_array`/`summing_int`, not literal Java
  camelCase). `min_by`/`max_by` reuse `check_comparator_result_type`
  (`sort.py`) and mirror `Stream._min_max`'s tie-break (first of equal
  elements wins) and `None`-on-empty-stream behavior exactly. `reducing`
  implements all three Java overload shapes — `reducing(binary_operator)`
  (no identity, mirrors `Stream.reduce(accumulator)`),
  `reducing(identity, binary_operator)` (mirrors
  `Stream.reduce(identity, accumulator)`), and
  `reducing(identity, mapper, binary_operator)` (maps each element before
  folding, argument order matching Java's
  `reducing(U identity, Function<T,U> mapper, BinaryOperator<U> op)`
  exactly) — dispatched via `@overload` + a runtime `_UNSET` sentinel, the
  same pattern `Stream.reduce` already uses. The loop bodies are
  intentionally duplicated from `Stream._min_max`/`reduce` rather than
  retrofitting those methods to accept an arbitrary `AsyncGenerator`, since
  a collector's contract has no `Stream` instance in scope and the loops are
  short and stable; `check_comparator_result_type` stays imported from
  `sort.py` as the single source of truth for the one piece of real shared
  logic. Discovered during implementation: the three `reducing` `@overload`
  stub bodies pushed combined branch coverage below the repo's 98% gate
  (each unreachable `def ...: ...` stub counts as a never-taken branch);
  fixed with `# pragma: no cover` on each stub line, an already-supported
  `exclude_lines` pattern in `pyproject.toml` — no config change needed.
  Added `tests/test_min_by.py`, `tests/test_max_by.py`,
  `tests/test_reducing.py`: extremum selection, empty-stream `None`,
  tie-break, async comparator/mapper/operator awaiting, `TypeError` on a
  bool-returning comparator, and all three `reducing` overloads including
  empty-stream/single-element edge cases. Updated README's `Collectors`
  table with three new rows. No breaking changes. See
  `openspec/changes/archive/2026-08-17-add-collectors-minby-maxby-reducing`.
- Added `counting()`, `summing_int`/`summing_long`/`summing_double`, and
  `averaging_int`/`averaging_long`/`averaging_double` (`collector.py`) —
  numeric reducing collectors, `collector.py`'s equivalent of the matching
  `Collectors` statics, following the same factory-returns-closure shape
  `joining()` established. `counting()` returns the `int` element count;
  `summing_int`/`summing_long`/`summing_double` map each element then sum
  the results (`int` for the first two, `float` for the last);
  `averaging_int`/`averaging_long`/`averaging_double` map each element and
  return the arithmetic mean as a `float` (`0.0` for an empty stream).
  Java's `Collectors` distinguishes `summingInt`/`summingLong`/
  `summingDouble` and the `averaging*` trio by primitive type — a
  distinction Python's numeric tower doesn't have — so each pair/trio is
  implemented identically apart from `summing_double`'s explicit `float()`
  coercion; kept as separate, Java-parity-named functions rather than
  collapsing to `summing(mapper)`/`averaging(mapper)`, since these are
  distinct Java method names (not one overloaded method, unlike `joining()`'s
  three arg-count variants). Added a new `NumberMapper` type alias to
  `type.py`. Mapper dispatch reuses the existing `_maybe_await` helper, so
  sync and async mappers both work. Added `tests/test_counting.py`,
  `tests/test_summing.py`, `tests/test_averaging.py`: non-empty/empty
  streams and sync/async mappers for each function, plus a `float`-type
  assertion for `summing_double`. Updated README's `Collectors` table with
  seven new rows. No breaking changes. See
  `openspec/changes/add-collectors-counting-summing-averaging`.
- Added `joining()` / `joining(delimiter)` / `joining(delimiter, prefix,
  suffix)` (`collector.py`) — a string-concatenation collector for use with
  `Stream.collect()`, `collector.py`'s equivalent of `Collectors.joining`
  and the first entry in the `Collectors`-parity effort tracked by this
  roadmap. Implemented as a single `joining(delimiter: str = "", prefix:
  str = "", suffix: str = "")` factory function, collapsing Java's three
  overloads into default arguments rather than `@overload`s, since the
  underlying behavior doesn't actually branch by argument count (contrast
  with `collect()`'s two genuinely different code paths, which do use
  `@overload`). It returns a plain `async def` closure over the composed
  `AsyncGenerator[str, None]`, matching `collector.py`'s existing
  plain-function collector shape (`to_list`/`to_generator`) rather than a
  callable class — no per-composition state is needed since
  prefix/delimiter/suffix are fixed at factory-call time. The join uses
  `delimiter.join(parts)`, so a non-`str` element naturally raises
  `TypeError` (matching Java's `Collectors.joining()`, defined only on
  `Stream<CharSequence>`) with no explicit `isinstance` check needed; an
  empty stream returns `prefix + suffix`, matching Java's Javadoc exactly.
  Added a new `Collectors` table section to README (none existed yet) to
  give this and future `Collectors`-family additions a place to be
  tracked. Added `tests/test_joining.py`: no-arg join, delimiter-only,
  delimiter+prefix+suffix, single-element (no delimiter applied), empty
  stream with and without prefix/suffix, and the `TypeError` regression for
  a non-`str` element. No breaking changes. See
  `openspec/changes/add-collector-joining`.
- Added `Stream.to_array()` (`stream.py`) — a terminal operation returning a
  `list` of every element pulled through the composed chain, functionally
  identical to `collect(to_list)`. Java's `toArray()`/`toArray(generator)`
  exist because arrays are a distinct, reified type from `List` and Java has
  no runtime generic-array construction; neither motivation applies to
  Python, where `list` is already the general-purpose ordered collection, so
  only the no-arg form was added — implemented as `to_array()` (snake_case),
  matching every other Java-name adaptation already in the class
  (`for_each`, `find_any`, `flat_map`), not the literal Java casing. The
  `toArray(generator)` overload was decided against and is documented in
  README as intentionally skipped rather than tracked as future work. Added
  `tests/test_to_array.py`: non-empty and empty streams, equivalence with
  `collect(to_list)`, `ParallelStream` coverage, and a `TypeError` regression
  for calling it with an argument. Updated README's parity table and
  removed the item from its "Left to do" list. No breaking changes. See
  `openspec/changes/add-stream-toarray`.
- Added `Stream.collect(supplier, accumulator, combiner)` (`stream.py`) —
  Java's 3-arg mutable-reduction overload of `collect()`, alongside the
  existing single-arg `collect(collector)` form. Implemented as an
  `@overload` pair dispatching on arg count, mirroring the precedent already
  set by `reduce()`'s identity/no-identity overloads: `supplier` is called
  once with no arguments to produce a fresh mutable container, `accumulator`
  is called once per pulled element as `accumulator(container, element)`,
  and both may be sync or async, dispatched via the existing `_maybe_await`
  helper. `combiner` is accepted for signature parity with Java but is
  never invoked — `collect()`, like the already-shipped `reduce()`, always
  folds over a single composed `AsyncGenerator` (sequential or parallel)
  with no independently-accumulated partitions to merge, so wiring up a real
  combine step is tracked separately in **Later** below, alongside the
  `.parallel()`/`PROCESSES` semantics decision it's blocked on. Added new
  `Supplier`/`BiConsumer` type aliases to `type.py`. Added 5 new tests in
  `tests/test_collect.py`: sync and async supplier/accumulator, an empty
  stream, and `combiner`-never-called coverage for both sequential `Stream`
  and `ParallelStream`. Updated README's parity table. No breaking changes.
  See `openspec/changes/archive/2026-08-17-add-collect-supplier-accumulator-combiner`.
- Added `Stream.for_each_ordered(consumer)` (`stream.py`) — an ordered variant
  of `for_each()`, invoking `consumer` in the stream's encounter order even
  when called on a `ParallelStream` instance, matching Java's
  `Stream.forEachOrdered()`. `for_each()` drives consumption via
  `self._compose()`, which `ParallelStream` overrides to fan the chain out
  across racing branches with no order guarantee; `for_each_ordered()`
  instead drives consumption via `self._sequential(self._chain[:],
  self._stream)` directly — the same building block `Stream._compose()`
  already uses — so it gets a strictly ordered, single-flight pull through
  the chain regardless of which subclass `self` is. This intentionally
  forfeits `.parallel()`'s concurrency for that one terminal call, the same
  trade-off Java's own `forEachOrdered()` makes on a parallel stream. The
  existing `BaseStream._ordered`/`unordered()` flag (see below) is not
  consumed here — every snakestream source has a real underlying order, and
  Java's own `forEachOrdered()` Javadoc ties the "if the stream has one"
  caveat to streams with no defined encounter order to begin with, which
  `unordered()` doesn't currently model. `for_each()`'s existing behavior is
  unchanged. Added `tests/test_for_each_ordered.py`: ordered/async-consumer
  coverage on sequential `Stream`, plus a same-chain-and-timing pair of
  parallel tests using a jumbled source and a positional (not value-based)
  per-element delay in a `.map()` step — one showing plain `for_each()` on a
  `ParallelStream` can come out scrambled under that reordering pressure, the
  other showing `for_each_ordered()` on the identical chain stays in source
  order. See `openspec/changes/add-stream-foreach-ordered`.
- Removed duplicate `_close_handlers` initialization. `BaseStream.__init__`
  (`base_stream.py`) always set `self._close_handlers = []`, but both
  `Stream.__init__` (`stream.py`) and `ParallelStream.__init__`
  (`parallel_stream.py`) immediately overwrote it with
  `close_handlers or []` right after `super().__init__(source)`, making the
  base assignment dead code on every instantiation. Fixed by giving
  `BaseStream.__init__` a `close_handlers` parameter and having it perform
  `self._close_handlers = close_handlers or []` directly; `Stream`/
  `ParallelStream` now just forward their own `close_handlers` argument via
  `super().__init__(source, close_handlers)` instead of reassigning the
  field themselves. No change to `on_close()`/`close()` or any observable
  behavior. Added a new `stream-close-handling` spec capturing the
  previously-undocumented `on_close()`/`close()`/construction/mode-switch
  contract, and new tests in `tests/test_close.py` covering scenarios not
  already exercised: registration order preserved across multiple
  `on_close()` calls, `close()` as a no-op with zero handlers registered,
  `Stream(source, [handler])` construction invoking the handler, and close
  handlers surviving a `.sequential()` switch (a `.parallel()` switch was
  already covered). See
  `openspec/changes/remove-duplicate-close-handlers-init`.
- Rewrote `BaseStream._sequential()` (`base_stream.py`) from recursion +
  `list.pop(0)` to an iterative loop over the queued closures. The old
  implementation recursed once per chained intermediate operation and
  popped from the front of the list on each call, giving O(n) Python stack
  depth (risking `RecursionError` on a long `.map()/.filter()/...` chain)
  and O(n²) time (since `list.pop(0)` is itself O(n), called n times) for a
  chain of n ops. Fixed by iterating the closures in order with a plain
  `for` loop and threading `iterable` through each step, dropping the
  `pop(0)` entirely — `_compose()` (`_sequential()`'s only caller) needed
  no changes since it already passes a fresh list copy. No change to
  `_sequential()`'s signature, return value, or `state_map` per-closure
  state lookup. Added `test_sequential_long_chain_does_not_recurse_at_build_time`
  (`tests/test_sequential.py`), calling `_sequential()` directly with a
  chain of `sys.getrecursionlimit() * 2` identity closures to isolate the
  build-time traversal this fix addresses.

  **Scope note, discovered during implementation:** this only fixes
  *building* the pipeline. Each individual op in `stream.py` (`filter`,
  `map`, `flat_map`, `sorted`, `peek`, `_DistinctOp`, `_LimitOp`,
  `_SkipOp`) is itself implemented as `async def fn(iterable): async for i
  in iterable: yield ...`, so *consuming* a long chain still recurses once
  per chained op at the `async for`/`__anext__()` delegation level,
  confirmed unchanged before and after this fix by testing a long
  `.map()` chain end-to-end. Fully closing the original roadmap item's
  stated risk requires a push-based execution-model redesign across every
  op in `stream.py` and `parallel_stream.py` — out of scope here and
  tracked as a new **Next**-bucket item. See
  `openspec/changes/rewrite-sequential-iterative`.
- Fixed `ParallelStream` crashing on any source with a real `await`
  suspension point. `ParallelStream._parallel` (`parallel_stream.py`) fanned
  `PROCESSES` racing branches out over the *same* shared `self._stream`
  async generator, each calling `__anext__()` on it independently; a source
  with a genuine `await` inside `__anext__()` raised
  `RuntimeError: anext(): asynchronous generator is already running` as soon
  as two branches' pulls overlapped. Fixed by adding a `_guarded(source,
  lock)` wrapper generator (`parallel_stream.py`): each branch gets its own
  wrapper instance, but all wrappers serialize their calls into the shared
  source's `__anext__()` (and `aclose()`) through one `asyncio.Lock` created
  per `_parallel()` call, so only one pull is ever in flight while
  downstream per-branch processing (`map`/`filter`/etc.) still runs
  concurrently. Fixing this surfaced a second, previously-latent race in
  `_LimitOp` (`stream.py`): its check-then-pull-then-increment sequence
  against the shared `size_holder` wasn't atomic once the pull could
  genuinely cede control, letting multiple branches pass the size check
  before any incremented and yield more than `n` elements in total. Fixed
  by reordering to reserve the slot (increment) *before* pulling, so the
  check-and-reserve step has no `await` between them and stays atomic
  across racing branches. Added `tests/test_parallel.py` coverage using a
  source with a real `await asyncio.sleep(0)` suspension point: empty and
  non-empty chains no longer raise, `.limit(n)` stays at-or-under `n` and
  closes the shared source safely across branches, and downstream mapper
  invocations still overlap despite serialized upstream pulls (timing
  assertion). No public API change. See
  `openspec/changes/fix-parallel-stream-await-crash`.
- Added `BaseStream.unordered()` — marks a stream instance as not
  order-dependent, mirroring Java's `BaseStream.unordered()`. Implemented as
  a `self._ordered: bool` flag on `BaseStream` (`base_stream.py`), defaulting
  to `True`; `unordered()` sets it `False` and returns `self`, matching the
  mutate-and-return-self convention every other chainable method already
  follows; `is_ordered()` exposes the current value, mirroring the existing
  `is_parallel()` query method. `sequential()`/`parallel()` now copy the
  flag onto the new instance they construct rather than resetting it, so an
  `unordered()` declaration survives a mode switch. Purely additive
  bookkeeping — no change to actual iteration order in `Stream` or
  `ParallelStream`; it exists to unblock the planned `forEachOrdered()` and
  `find_first()`/`find_any()` distinction (`stream.py`'s disabled
  `find_first` stub), neither of which consume the flag yet. Added
  `tests/test_unordered.py` covering: ordered-by-default for both `Stream`
  and `ParallelStream`, `unordered()` mutation and chaining (returns `self`,
  composes with other intermediate ops), isolation across separate `Stream`
  instances, and flag propagation across `.parallel()`/`.sequential()` mode
  switches (both directions, with and without `unordered()` called). See
  `openspec/changes/add-stream-unordered`.
- Added `BaseStream.iterator()` — exposes the composed stream chain as a
  plain `AsyncGenerator` without going through a collector, so a caller can
  drive consumption directly via `async for`, `__anext__()`, or partial
  iteration. Implemented as a thin wrapper around the existing `_compose()`
  mechanism already used by terminal operations (`base_stream.py`), so it
  works identically for `Stream` (sequential) and `ParallelStream` (parallel)
  with no subclass-specific override, and — like other terminal ops —
  composes non-destructively, leaving `self._chain` intact for later reuse.
  Added `tests/test_iterator.py` covering: no elements pulled before
  iteration starts, same elements/order as `collect(to_list)` for an
  equivalent chain, partial consumption, `ParallelStream` behavior (racing
  branches, unordered), and non-destructive composition (a second terminal
  op after `iterator()` still sees the full chain). No public API removal;
  purely additive. See `openspec/changes/archive/2026-08-13-add-stream-iterator`.
- Added `Stream.reduce(accumulator)` — the 1-arg, no-identity overload,
  returning `T | None` (`None` for an empty stream) rather than a wrapped
  `Optional[T]` type, matching the existing `find_any()`/`max()`/`min()`
  convention already used elsewhere in `stream.py`. Implemented as a single
  `reduce()` method carrying two `@overload` signatures (identity form and
  no-identity form) with one runtime body: a private `_UNSET` sentinel
  distinguishes "no identity given," in which case the first pulled element
  seeds the fold and an empty stream short-circuits to `None` before the
  accumulator is ever called; a single-element stream likewise returns that
  element without calling the accumulator. Delegates to the same
  `_maybe_await`-based accumulator dispatch the 2-arg form already used, so
  sync and async accumulators both work with no duplicated dispatch logic.
  Added a new `BinaryOperator` alias to `type.py` for the no-identity
  accumulator's `T, T -> T` shape, following the project's convention that
  composite/callable type shapes used in public signatures live in
  `type.py` rather than being written inline. Added 6 new tests in
  `tests/test_reduce.py` (empty stream, single-element stream, multi-element
  fold order, async-accumulator awaiting, a hypothesis property test against
  `functools.reduce`, and a regression check that the existing 2-arg form is
  unchanged). No changes to the existing `reduce(identity, accumulator)`
  behavior. See `openspec/changes/add-reduce-no-identity`.
- Added `Stream.skip(n)` — drops the first `n` elements pulled from upstream
  and yields the rest, symmetric with the already-implemented `limit(n)`.
  Implemented as `_SkipOp` (`stream.py`), mirroring `_LimitOp`'s
  `make_state()`/shared-state pattern so `ParallelStream._parallel()`'s
  existing generic `make_state()`-detection wires up correct parallel
  behavior (exactly `n` total elements dropped across all racing branches,
  not per-branch) with no `parallel_stream.py` changes needed. Unlike
  `limit()`, `skip()` has no short-circuit available — the first `n`
  elements must actually be pulled and discarded to advance upstream past
  them. Added `tests/test_skip.py` plus parallel-specific regression tests
  in `tests/test_parallel.py` (drops exactly `n` across branches, state
  fresh across separate streams). No public API change to existing methods.
  See `openspec/changes/add-stream-skip`.
- Made `Stream` generic (`Stream[T]`): `BaseStream`/`Stream`/`ParallelStream` were
  plain classes, so the `T`/`R` in their method signatures were unbound
  `TypeVar`s and element types were `Unknown` end to end — `ty` accepted
  `Stream.of([1,2,3]).map(lambda s: s.upper())` without complaint despite
  `int` having no `.upper()`. Fixed by making `BaseStream`/`Stream`/
  `ParallelStream` `Generic[T]`; `map()`/`flat_map()` now return `Stream[R]`
  via a narrowly-scoped `cast(Stream[R], self)` since the chain-of-closures
  model mutates and returns the same `self` rather than a new instance
  (deliberately not revisiting the separate mutable-builder-vs-immutable-
  pipeline decision below); type-preserving ops (`filter`, `distinct`,
  `peek`, `limit`, `sorted`) return `Stream[T]` directly; terminal ops are
  typed against the stream's bound `T`. Also fixed `type.py`'s `FlatMapper`
  alias, which hardcoded an unparameterized `Stream` instead of `Stream[R]`,
  and `StreamBuilder.build()`, which dropped its already-declared `T`
  instead of returning `Stream[T]`. Typing-only change, no runtime behavior
  differs. Added `tests/test_static_typing.py` plus `tests/typing/`
  fixtures that shell out to `ty check` to regression-test that the
  motivating bug is now caught and that valid generic usage still
  type-checks cleanly. See `openspec/changes/make-stream-generic`.
- Made `limit(n)` a real short-circuit: `_LimitOp.__call__` (`stream.py`) pulled
  an element from upstream *before* checking whether `max_size` had already
  been reached, so every `limit(n)` pipeline pulled `n+1` elements instead of
  `n` — e.g. `Stream.of([1,2,3,4,5]).peek(seen.append).limit(2)` returned
  `[1, 2]` but left `seen == [1, 2, 3]`. Fixed by checking the size before
  pulling rather than after, so upstream is closed without ever pulling an
  `n+1`th element. Under `.parallel()`, the shared `size_holder` in
  `ParallelStream._parallel`'s `state_map` already gave a global (not
  per-branch) limit guarantee; the fix changes *when* the shared source gets
  closed — whichever branch observes the shared count reaching `max_size`
  closes it before pulling further — and closure was made idempotent so a
  second racing branch closing (or pulling from) an already-closed shared
  source doesn't raise out of the task loop. No public API change. See
  `openspec/changes/archive/2026-08-12-fix-limit-short-circuit`.
- Replaced the repeated `if iscoroutinefunction(x): await x(...) else: x(...)`
  dispatch pattern (10 sites across `filter`, `map`, `sorted`'s comparator,
  `peek`, `reduce`, `for_each`, `min`/`max` via `_min_max`, and the
  `all_match`/`any_match`/`none_match` family) with a single
  `async def _maybe_await(fn, *args)` helper in a new
  `callable_dispatch.py`, which calls first and awaits the result only if
  `inspect.isawaitable(result)`. Fixes a real bug: `iscoroutinefunction()`
  is `False` for a class instance with an `async def __call__`, so passing
  such a callable object as a predicate/mapper/etc. previously produced an
  un-awaited coroutine flowing downstream as if it were a real value, with
  only a `RuntimeWarning` — no exception. `flat_map`'s existing
  `iscoroutinefunction()` check, which *rejects* coroutine-returning
  mappers up front, is a distinct pre-call classification and was left
  untouched. Also collapsed `all_match`/`any_match`/`none_match`'s three
  near-identical bodies into one shared `_match(predicate, short_circuit_on,
  default)` helper built on `_maybe_await`.

  `sorted()`'s comparator dispatch turned out not to fit the same
  call-then-await shape: its `iscoroutinefunction()` check picks between
  two different sort algorithms (`merge_sort`, which unconditionally
  awaits the comparator, vs. `list.sort()` with a sync `cmp_to_key`
  wrapper) rather than gating a single await. Fixed by moving `_merge`
  (`sort.py`) onto `_maybe_await` internally and always routing `sorted()`
  through `merge_sort` when a comparator is given, dropping the
  `cmp_to_key`/`list.sort()` branch entirely — this also closes the same
  async-callable-object gap for `sorted()`/`min()`/`max()`. Added
  regression tests (`tests/test_callable_dispatch.py`) covering
  `_maybe_await` directly (sync/async function, sync/async callable
  object) and each affected operation with an async-`__call__` callable
  object.
- Fixed two compounding bugs that made a second terminal operation on the
  same `Stream`/`ParallelStream` instance silently return wrong (usually
  empty) results instead of repeating the first run's behavior. First,
  `BaseStream._sequential()` (`base_stream.py`) was handed `self._chain`
  directly and called `pop(0)` on it, draining the caller's own chain list
  during `_compose()`; fixed by passing `self._chain[:]` (a copy) from
  `_compose()` instead — matching the copy `ParallelStream._parallel()`
  already made for its own branches, so both subclasses now honor the same
  non-destructive contract. Second, `distinct()`/`limit()` (`stream.py`)
  each built their `seen`/`size` state in the outer function that runs once
  per `.distinct()`/`.limit()` call, rather than in the closure that runs
  once per composition, so that state silently persisted across separate
  compositions of the same chain; fixed by replacing the two closures with
  small callable classes (`_DistinctOp`, `_LimitOp`) whose `__call__` takes
  an optional external state and falls back to fresh per-call state via
  their own `make_state()` when none is given — giving `Stream` (sequential)
  fresh state on every composition by default. For `ParallelStream`, where
  multiple racing branches must share one `seen`/`size` per composition to
  stay globally correct (matching Java's guarantee that parallel `distinct`/
  `limit` never silently degrade into a per-partition, unreconciled result,
  even though it costs more to coordinate — see
  `openspec/changes/fix-stream-rerun-state/design.md`), `_parallel()` now
  builds one state map per composition via each op's `make_state()` and
  passes the same map into every racing branch's `_sequential()` call.
  Added regression tests covering: chain length unaffected by composition,
  a second terminal op after the first, `distinct()`/`limit()` state not
  leaking across separate `Stream`/`ParallelStream` instances or across
  separate compositions of one instance, and parallel `distinct()`/`limit()`
  staying globally correct (no cross-branch duplicates, no over-`limit()`)
  across racing branches.
- Simplified `Stream.of()` (`stream.py`) from a four-way branch on dict vs.
  list vs. multiple positional args vs. kwargs down to two cases: a single
  positional arg passes straight through to `Stream()`'s existing source
  normalization, multiple args wrap into a list (one element each). The
  dict/list `isinstance` special-casing turned out to be dead complexity —
  tracing all 15 existing `test_of.py` cases showed it always produced the
  same call as the generic path, since `_normalize()` already re-spreads
  lists/dicts on its own. Also fixed `_normalize()` (`base_stream.py`) to
  treat `str`/`bytes` as scalar values, matching how Java's `Stream.of(T...)`
  treats `String`/`byte[]` atomically (byte arrays can't decompose via
  varargs since `T` can't bind to a primitive type), instead of the previous
  silent char-by-char/byte-by-byte spreading. Both changes are **BREAKING**
  and tracked in README's migration log per `CLAUDE.md`: `**kwargs` support
  is removed from `Stream.of()` entirely (no Java equivalent, undiscoverable,
  no real use case over `Stream.of(*some_dict.items())`), and
  `Stream.of("abc")`/`Stream.of(b"ab")` now yield one element instead of
  spreading.
- Added property-based tests with `hypothesis` for `map`, `filter`, `reduce`,
  `sorted`, `distinct` against a plain-Python reference oracle, covering
  edge cases hand-written tests miss (empty/single-element streams,
  duplicate keys, async callables).
- Added a `check_comparator_result_type()` runtime guard (`sort.py`) that
  raises `TypeError` if a user-supplied `Comparator` returns `bool` instead
  of `int`, used by `Stream._min_max()` (backing `min()`/`max()`) and both
  branches of `Stream.sorted()` (sync `cmp_to_key` path and the async
  `merge_sort`/`_merge` path). Closes a gap the earlier `Comparator`
  contract fix (below) didn't cover: Python's `bool` is a subclass of `int`,
  so a bool-returning comparator like `lambda x, y: x > y` type-checks fine
  under `ty`/mypy/pyright and previously degraded silently instead of
  erroring — for `min()` it could never signal "orders before" (always
  returning the first element), while `max()`'s behavior happened to be
  correct by coincidence. No static-typing trick can close this gap since
  it's structural to Python, not a `type.py` alias choice. Also fixed 18
  pre-existing tests across `tests/test_min.py`/`tests/test_max.py` that
  were passing bool comparators and only passed today via first-element
  luck (`min()`) or coincidence (`max()`); added regression tests asserting
  the `TypeError` for `min()`/`max()`/`sorted()`, sync and async. Tracked as
  **BREAKING** in README's migration log per `CLAUDE.md`.
- Fixed the `Comparator` type alias mismatch (`type.py:16`): kept a single
  Java-style 3-way *int* `Comparator` (matching `sorted()`'s existing usage
  and Java's own `Stream.min/max(Comparator)`), rather than splitting into
  two aliases, and fixed `Stream.min()`/`max()`/`_min_max()` (`stream.py`)
  to interpret the comparator's sign directly instead of treating it as a
  bool. This also fixed the tie-break bug for free: both `min()` and `max()`
  now keep the first of equal elements. Tracked as **BREAKING** in README's
  migration log per `CLAUDE.md` since bool-returning comparators passed to
  `min()`/`max()` now behave differently.
- Added an `install_smoke_test` CI job (`.github/workflows/check.yml`) that,
  for each of Python 3.10–3.14, creates a clean venv (`uv venv`, not
  `uv sync`), runs `pip install .` against the built package, and imports
  `snakestream` from outside the repo checkout — catching packaging
  mistakes that the source-tree `pytest` job wouldn't.
- Added static type checking to CI using `ty`, Astral's newer Rust-based
  type checker — chosen over `mypy`/`pyright` since it fit the existing
  `uv`/`ruff` toolchain and handled the codebase's `Awaitable`-union type
  aliases without issue. Fixed the 6 genuine type errors it surfaced
  (`BaseStream.on_close`'s return type, `ParallelStream`'s task-list
  typing, `StreamBuilder`'s unbound `TypeVar`, `Stream.collect`'s generic
  return type, and `Stream._min_max`'s sentinel-return typing), plus one
  scoped `ty: ignore` for a case the checker can't narrow via the
  runtime `iscoroutinefunction()` check in `Stream.sorted`. Gated to the
  3.14 matrix leg only, matching the coverage-gate precedent.
- Verified `--cov-fail-under=98` already enforces combined line+branch
  coverage, not line coverage alone: `[tool.coverage.run] branch = true`
  folds branch-arc misses into the same "percent covered" figure the gate
  reads, confirmed by observing a deliberately partial branch drop the
  reported percentage. No code change needed; added a comment in
  `pyproject.toml` recording the finding so it doesn't need re-deriving.
- `min()`/`max()` used to silently skip falsy candidate values (`0`, `""`,
  `False`) because of a truthiness check in `Stream._min_max`. Fixed by
  replacing the `None`-as-sentinel logic with a proper `_UNSET` sentinel.
- `parallel()` pipelines left orphaned `asyncio` tasks (and "Task exception
  was never retrieved" warnings) when one branch raised mid-stream. Fixed in
  `ParallelStream._parallel` by cancelling and draining remaining tasks in a
  `finally` block.
- Test infra was silently dropping tests on a clean install: `pytest-mock`
  was missing from `setup.cfg`'s `testing` extra, and the `async_int_to_letter`
  fixture in `conftest.py` wasn't decorated for strict-mode `pytest-asyncio`.
  Both fixed; added regression tests for the two bugs above
  (`test_min.py`, `test_max.py`, `test_exception.py`).
- `Stream.of()` had a dead branch, `if args and len(args) == 0: pass`
  (`stream.py:40-41`), which could never be true and just duplicated the
  no-op fallthrough of the `else` branch. Removed.
- The `TYPE_CHECKING`-only import in `stream.py:17` used an unqualified
  `from stream_builder import StreamBuilder`, which would fail if ever
  actually evaluated. Fixed to `from snakestream.stream_builder import
  StreamBuilder`.
- Added tests covering the async-predicate short-circuit branches of
  `all_match`, `none_match`, and `any_match` (`stream.py:255,267,283`) that
  were previously only exercised by synchronous predicates.
- Added a `--cov-fail-under=98` gate so a coverage regression now fails CI
  instead of silently passing. Enforced only on the newest Python version
  in `check.yml`'s matrix (not via `setup.cfg`'s `addopts`), since
  `coverage.py`'s branch-arc measurement for `async for` loops differs
  across CPython versions and produced spurious failures on 3.8/3.9.
- Fixed `deliver.yml` to target `master` instead of `main`, since the repo's
  default branch is `master` and the workflow was never triggering.
- Pinned GitHub Actions to commit SHAs and added concurrency guards to CI
  workflows.
- Added `pip-audit` dependency-vulnerability scanning and `ruff format`
  enforcement to CI.
