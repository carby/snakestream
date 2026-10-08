+++
id = "make-combiners-live"
title = "Collector combiners become live (`make-combiners-live`)"
filed = 2026-09-04
closed = 2026-09-04
outcome = "shipped"
shipped_as = "make-combiners-live"
+++

**`make-combiners-live`** (2026-09-04) — the last of the three items the
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
