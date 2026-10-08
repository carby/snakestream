+++
id = "ramp-batch-growth-geometrically"
title = "Ramp fork/join's batch growth instead of jumping to it"
filed = 2026-08-20
closed = 2026-09-07
outcome = "shipped"
shipped_as = "ramp-batch-growth-geometrically"
+++

**Ramp fork/join's batch growth instead of jumping to it** (closed 2026-09-07;
filed 2026-08-20, split 2026-09-06 from "Bound speculation separately from
read-ahead" once that item's benchmark answered the sizing question it had
left open). Shipped as `ramp-batch-growth-geometrically`.

All three fork/join call sites — `_fork_join_ordered_batches()`,
`_fork_join_unordered_batches()`, and a **third site found only during
implementation**, `_fork_join_partitioned()` (task 1.1), which ran the
identical one-step 4 -> 1024 jump through `_pull_round()` and was missed by
both the roadmap item and design.md's decision 5, which named only the first
two — now seed at one element per worker and grow `size = min(size * 8,
BATCH_SIZE)` per refill. `_FIRST_BATCH_SIZE` is deleted; seeding at 1 measured
strictly better than the old 4 and needs no named constant.

**Task 7.2's rejection of a smoother growth curve (`fork-join-executor-and-
spliterator`) stands and does not transfer to this one.** 7.2 measured a
Java-style *arithmetic* ramp (`+4`/round): 126 dispatches against the shipped
12 at n=8192, never saturating, so its dispatch count is O(n) in the source
length. This change's *geometric* ramp saturates in `log_8(1024)` ≈ 4 refills
— after that it *is* the shipped rule — so its extra cost is a small,
source-independent constant rather than a multiplier that grows with n. That
distinction was never tested before this item, and it inverts 7.2's verdict:
a smoother curve was worse for the rule 7.2 tried and is not worse for this
one.

Reproduced against the landed code, not the prototype the design's figures
came from: shipped one-step dispatch counts (n=200/8192/100000 -> 5/12/102)
reproduced exactly; the geometric ramp measured 10/19/109 — a +7 toll at
n=100000, matching the design's gate exactly, and a slightly smaller toll
than claimed at n=8192. The seed-1 waste-column table (`@k=1` -> 4, `@17` ->
35, `@20` -> 59) reproduced closely only at `k=1`; `k=17`/`k=20` were noisy
and run-to-run variable on the landed code (tens to low hundreds, never
anywhere near the old code's ~4096), because the order-blind path's waste
depends on genuine concurrent completion order that the design's own
prototype apparently did not exercise at the same variance. Recorded as a
divergence rather than argued away; it does not affect the gate, which is the
dispatch-count figure above.

`find_first()`'s documented over-invocation bound tightens from `WORKERS *
_FIRST_BATCH_SIZE` (16) to `WORKERS` (4); `stream-find-first`'s spec no
longer names the deleted symbol. No README Migration entry: the bound is one
the specs already declare retunable, and no public name moved.
`spread-small-sources-across-workers`, sequenced after this item, had its
`_FIRST_BATCH_SIZE=4` / "round one covers 16" premise noted as superseded in
place, without restructuring that peer's proposal.
