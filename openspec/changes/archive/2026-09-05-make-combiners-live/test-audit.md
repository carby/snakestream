# Inverse spec sweep — task 5

The prior change (`fork-join-executor-and-spliterator`) audited whether
*deleted* tests still mapped to surviving requirements. This change adds a
new execution path instead (the fork-join executor's partitioned `value()`
override), so the risk runs the other way: does an *existing* spec still
hold against code the whole collector suite was, until now, never run
against. Swept `openspec/specs/` for every capability the proposal's own
Risks section named, plus the per-collector capabilities gaining or
declining a combiner.

| Spec | Verdict | Notes |
|---|---|---|
| `callable-dispatch` | needed a delta | "classified once per composition" didn't anticipate a partitioning terminal rebuilding a sink per **batch** (`new_partition()`), a second reconstruction pattern alongside the fork-join per-element sink the requirement already covers. Delta adds the rule and a scenario; `CollectorSink`/`ReduceSink` now thread `is_async` through `new_partition()` so classification runs once, not once per batch — verified by `test_classification_is_not_repeated_per_element_under_fork_join`, which failed (8 calls vs. 3) before that fix. |
| `collector-protocol` | needed a delta | "`combiner` is accepted but never invoked" is now false outright; replaced with the partitioning rule. |
| `mutable-reduction-collect` | needed a delta | same false statement for the 3-arg `collect()` form. A peer-session review caught a real defect at this surface before archive: the first `merge_from()` required a returning `BinaryOperator` unconditionally, silently breaking the `BiConsumer` type this library itself declares (`stream.py`) and Java's own `Stream.collect(Supplier, BiConsumer, BiConsumer)` convention (`list.extend` is Java's own documented example) — `AttributeError` from library internals for any caller following the declared signature, under `.parallel()` only. Fixed by reading a `None` merge result as "mutated in place" rather than as the new container; both of Java's two combiner conventions now work. The one place an existing call site's *result* legitimately changes is a genuinely non-associative `combiner`, not this. |
| `terminal-sinks` | needed a delta | "the terminal SHALL receive every element" no longer holds literally for a partitioning terminal's own `accept()` (peers receive elements; the terminal only receives merges) — delta restates the guarantee at the accumulation level and adds the partitioned-loop's cancellation checks explicitly. |
| `stream-execution-model` | needed a delta | the terminal-driving operation's docstring-turned-spec text asserted the fork-join executor's use of the generic form was **not merely a measurement result** but a structural necessity ("exactly the `Collector` combiner this library does not yet drive") — this change is precisely that combiner arriving, so the paragraph was rewritten to describe the new conditional override instead of asserting its impossibility. |
| `comparator-contract` | still true | governs `Stream.min()`/`max()`'s own `MinMaxSink`, which this change does not touch — `MinMaxSink` never gained a partition protocol, so it stays on the unchanged path. Not to be confused with `min_by()`/`max_by()` (the collectors), covered separately below. |
| `sink-protocol` | needed a delta | added the partition protocol's shape (`can_partition()`/`new_partition()`/`merge_from()`) as new clauses on "Terminal sink produces a result", with the base declining by default. |
| `parallel-reduction` | new capability, N/A | this change's own spec; not swept against itself. |
| `collector-min-max` | needed a delta | new combiner requirement, including the tie-break-preservation scenario task 4.2 and 5.4 both ask for — verified against `is_new_extremum`'s existing left-biased contract rather than reimplemented. |
| `collector-to-set`, `collector-joining`, `collector-counting-summing-averaging`, `collector-summarizing`, `collector-reducing`, `collector-to-map`, `collector-to-collection`, `collector-grouping-by`, `collector-partitioning-by`, `collector-mapping`, `collector-collecting-and-then` | needed a delta each | new combiner (or explicit non-combiner) requirement per task 4's enumeration; see each spec file under this change's `specs/` for the individual requirement and scenarios. |
| `racing-encounter-order` | still true | describes the delivery-barrier mechanism `split_point()`/`ordering.py` implement, which this change reuses unmodified (gating the partitioned path on the same `split_point()` search, with `OrderDemand.NONE` to disable its terminal-driven clause — see `_ForkJoin.value()`'s docstring). No requirement there assumed the fork-join executor's terminal-driving operation had only one implementation. |
| `stream-ordering`, `pipeline-composition`, `pipeline-immutability`, `stream-spliterator` | still true | none of these govern terminal-side accumulation; `_fork_join_partitioned()` reuses `_pull_round()`/`spliterator.BATCH_SIZE` unmodified, so their guarantees (contiguous batches, chain reuse, derive-without-reinit) carry over as-is. |

## Task 5.3 — callable-dispatch's per-composition classification on the partitioned path

Verified directly: `test_classification_is_not_repeated_per_element_under_fork_join`
(`tests/test_callable_dispatch.py`) counts `is_async_callable` calls across a
`.map().filter().collect(to_list())` pipeline, sequential vs. parallel, and
asserts equality. `to_list()` gained a combiner in this change, so this test
now also exercises the partitioned path (5 batches over 500 elements at the
defaults) — it caught the regression described above before the
`new_partition(is_async=...)` fix.

## Task 5.4 — comparator-contract's tie-breaking under partitioning

`min_by`/`max_by`'s collector-level tie-break is governed by
`collector-min-max`, not `comparator-contract` (which is `Stream.min()`/
`max()`'s own, unaffected — see the table above). Verified by
`test_min_by_keeps_first_of_tied_wins_under_partitioning` and
`test_min_by_combine_awaits_an_async_comparator`
(`tests/test_collector_combiners.py`): every element compares equal under
the test comparator, so the returned element is decided entirely by the
tie-break, and the parallel result matches the sequential one — the earliest
element in encounter order, across partition merges as well as within one.
