# Benchmark findings — task 7

Measured 2026-09-04, `uv run python` (3.14.5, GIL-enabled build — `sys._is_gil_enabled()` reports `True` on this machine's default interpreter; unlike `fork-join-executor-and-spliterator`'s benchmark, no free-threaded leg was run here, so these figures are the GIL-build story only). Every number is a `statistics.median` of 5 in-process trials, warm interpreter.

## Task 7.1 — the proposal's own benchmark, re-run against this change

Same four shapes as `proposal.md`'s table, `n=4000`, 4 workers, `asyncio.sleep(0.0002)` standing in for the "slow" classifier/mapper (I/O-bound, so it releases the GIL — the same reason the fork-join executor's I/O numbers scale on the GIL build too, per `fork-join-executor-and-spliterator`'s own findings):

| where the work is | sequential (median) | parallel (median) | speedup |
|---|---:|---:|---:|
| in the chain — `.map(slow).collect(to_list())` | 5550.4ms | 53.1ms | **104.52x** |
| in the collector — `grouping_by(slow_key)` | 5585.0ms | 1431.5ms | **3.90x** |
| in the collector — `to_map(slow_key, cheap)` | 5566.1ms | 1432.7ms | **3.89x** |
| trivial collector — `.map(slow).collect(counting())` | 5403.1ms | 54.0ms | **100.06x** |

**The two rows this change exists to move now scale.** `grouping_by(slow_key)` and `to_map(slow_key, cheap)` went from 0.98x/0.99x (proposal.md, no parallelism at all for collector-internal work) to 3.90x/3.89x. They land well under the chain-only and trivial-collector rows' triple-digit speedups, for a reason that is not a defect: `grouping_by`/`to_map` still run their classifier once per element *inside* `accept()`, sequentially within a batch (`_run_partition_sync()` reuses `_run_batch_async()`'s per-element racing for the *chain*, but a partitioning terminal's own accumulation is necessarily sequential per batch — a terminal's `accept()` is not safe to call concurrently, see `sink-protocol`'s partition protocol and `execution.py`'s `_run_partition_sync()` docstring). The classifier here sits in the *collector's* accumulator, not the chain, so it does not get the intra-batch `gather()` concurrency the chain rows do — only cross-batch (thread-level) concurrency, bounded by `WORKERS=4`. That bound is consistent with the ~4x ceiling observed.

Absolute numbers are not directly comparable to `proposal.md`'s (that benchmark used a real blocking-shaped workload at `n=4000`, this one uses `asyncio.sleep` at a shorter duration and a slightly different machine load) — the ratio each row moved, not the absolute milliseconds, is the finding task 7.1 asks for.

## Task 7.2 — does the combiner pay for a cheap accumulator

The concern design.md's Risks section raised: `counting()`'s merge is "an addition against an addition," and might cost more than it saves. Measured `n=8192`, a cheap sync `.map(identity)` forcing real batch dispatch (a chain-free `.parallel().collect(...)` degenerates to a fully sequential single pass via `split_point()`'s empty-chain case — a pre-existing property of `_fork_join_through()`, unrelated to this change, and not a fair comparison; the `.map(identity)` op is there specifically to avoid that trap):

| call | median |
|---|---:|
| `.parallel().map(identity).collect(to_list())` — combinable | 65.74ms |
| `.parallel().map(identity).collect(<no-combiner list collector>)` — never partitions | 85.19ms |
| `.parallel().map(identity).collect(counting())` — combinable | 76.48ms |
| `.parallel().map(identity).count()` — no collector at all | 85.30ms |

**The combiner does not pay here — it is a net win, not a net loss, for both cheap collectors measured.** `to_list()`'s combinable path is ~19ms faster than an otherwise-identical collector with no combiner; `counting()`'s is ~9ms faster than `count()`. The likely reason: the non-partitioning path still composes through `elements()`'s `AsyncGenerator` layer (`_fork_join_through()` yielding into `_drain()`), where the partitioned path accumulates directly per batch with nothing buffered between a batch's chain output and its peer container. Task 7.2's conditional — "a collector where merging measurably costs more... should have its combiner removed" — does not apply to any collector gaining one in this change; none is removed.

## Task 7.3 — no regression against the pre-change path

The "no-combiner" rows in the task 7.2 table stand in for the pre-change tree without a separate checkout: before this change, every collector's `combiner` was inert, so `to_list()`/`counting()` always drove through the same generic `_drain(elements(...), terminal)` path the no-combiner collector still uses today (`can_partition()` is what gates the new path, and a `Collector` built with no `combiner` is exactly what every collector used to be). Both measured combinable collectors are faster than that baseline, not slower — no regression, on this proxy.

## Task 7.4 — the merge does not dominate here, so the Open Question is unmeasured

design.md's Open Question — whether a coarser partition (one per *worker* rather than per *batch*) would help — is asked in case the merge dominates for cheap accumulators. It does not, per task 7.2 above: the batch-per-partition granularity `_pull_round()`/`_fork_join_partitioned()` already uses is not the bottleneck for either collector measured, so there is nothing here to record against that question. It remains open, unresourced by this change's numbers, exactly as design.md leaves it.
