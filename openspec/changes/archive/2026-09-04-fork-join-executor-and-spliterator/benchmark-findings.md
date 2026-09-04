# Benchmark findings — task 7.2

Measured 2026-09-04, on the same machine, comparing the pre-change racing
executor (`git worktree` at `a872f25`, the commit immediately before this
change's work began) against the current fork-join tree, using the same
harness against both. Every number below is a `statistics.median` of 3-5
in-process trials (warm interpreter, not per-process cold starts).

`uv run python` on this machine resolves to a free-threaded interpreter by
default (a `uv` Python-discovery quirk, not a project setting) — every figure
below states which interpreter actually ran, forced with
`uv run --python /usr/local/bin/python3.14` for the GIL build and
`uv run --python 3.14t` for the free-threaded one, after the default was
caught giving a misleading first pass.

## Four mapper shapes, GIL-enabled build (3.14.5, `gil=True`)

| mapper | n | sequential (median) | parallel (median) | seq/par ratio |
|---|---:|---:|---:|---:|
| sync cheap (`x + 1`) | 8192 | old: 4.10ms / new: 4.24ms | old: 80.13ms / new: 92.30ms | old: 0.05x / new: 0.05x |
| sync CPU-bound (4000-iteration inner loop) | 8192 | old: 1557.66ms / new: 1512.43ms | old: 1673.37ms / new: 1590.33ms | old: 0.93x / new: 0.95x |
| async I/O (`asyncio.sleep(0.001)`) | 400 | old: 554.11ms / new: 556.63ms | old: 145.22ms / new: 10.31ms | old: 3.82x / **new: 54.00x** |
| async cheap (`x + 1`) | 8192 | old: 4.65ms / new: 4.60ms | old: 80.98ms / new: 78.14ms | old: 0.06x / new: 0.06x |

**I/O-bound work is the standout win** — 54x speedup where the old racing
executor got 3.8x. The old executor bounded read-ahead at 16 elements
in-flight (`_IN_FLIGHT_PER_WORKER=4` × 4 workers); fork-join's steady state is
`WORKERS * BATCH_SIZE` = 4096, so an I/O-bound source this size is
essentially fully in flight rather than trickling through a 16-wide window.

**Cheap-mapper regression is real, unchanged in *ratio* from the old
executor, but the *absolute* cost at this `n` is far larger than design.md's
Risks section estimated.** design.md says "the worst measured case is +1.5ms
on a 0.3ms pipeline, bounded at O(workers)". At `n=8192` the actual regression
is ~83-88ms (new tree, `4.24ms → 92.30ms`) — two orders of magnitude larger
than +1.5ms, and it does **not** stay bounded at O(workers): see the
batch-dispatch-count measurement below, which is the actual driver. Both old
and new pay a similarly-shaped regression here (0.05x-0.06x either way), so
this is not a fork-join-specific *new* problem — the old racing executor's
per-element `asyncio` task overhead was comparably expensive relative to
`x + 1` — but the design.md figure needs correcting since it understates the
cost at realistic `n`. Fixed in the same commit as this file (see design.md's
updated Risks entry).

**Correction, after a cross-session review caught a second, real bug in the
same neighbourhood (2026-09-04):** `execution._run_element()` builds a fresh
sink chain per element, and `FilterOp`/`MapOp`/`PeekOp`'s sinks were each
re-running `is_async_callable()` in their own `AsyncDispatch._init_dispatch()`
— once per element per op, not once per composition, violating
`callable-dispatch`'s "Awaitability is classified once per composition"
requirement outright (1001 calls for 500 elements through `map`+`filter`,
against 3 sequentially — independently reproduced, then fixed by classifying
once on the `Op` instead: see `callable-dispatch`'s spec delta and
`ops.py`'s `_SinglePureCallableOp`). Re-measured the cheap-mapper case after
the fix: `92.30ms → 76.11ms` at `n=8192` — a real but modest ~18ms
improvement, consistent with the reviewer's own estimate that classification
was roughly a third of the per-element overhead (`_run_element`'s per-element
sink construction and the batch-dispatch cost below account for the rest,
and are not fixed by this — the review explicitly agreed that part should
stay). The **83-88ms figure above is now stale**; the current, post-fix
regression at `n=8192` is ~72ms (`4.08ms → 76.11ms`). The batch-dispatch-count
explanation below is unaffected by this fix — it was never about
classification — and remains the larger of the two costs.

**CPU-bound work sees no change on the GIL build** (0.93x old vs 0.95x new,
both statistically a wash) — expected, since neither executor gets real
parallelism there: the old one never used threads, and the GIL serializes
Python bytecode across the new one's threads too.

## CPU-bound work, free-threaded build (3.14t, `gil=False`)

| n | sequential (median) | parallel (median) | speedup |
|---:|---:|---:|---:|
| 200 | 10.23-10.80ms | 13.91-15.91ms | **0.7x (slower)** |
| 4096 | 249.07-249.28ms | 120.94-136.77ms | **~1.9x** |
| 8192 | 496.34-515.54ms | 252.46-253.72ms | **~2.0x** |

This is the real payoff `.parallel()` never had before this change: genuine
CPU parallelism, on the free-threaded build, for CPU-bound work — something
no version of the old racing executor (task-based, single event loop) could
give at any worker count. It does **not** show up at `n=200`: with `WORKERS=4`
and `_FIRST_BATCH_SIZE=4`, round 1 covers only 16 elements, and round 2's
jump straight to `BATCH_SIZE=1024` means the entire 184-element remainder
lands in a *single* worker's batch (`batch()` drains up to 1024 from one
shared iterator before the next worker gets a turn) — so only one thread ever
does real work, and dispatch overhead alone makes it slower than sequential.
The growth curve's shape controls this cliff directly; see the next section.

**Correction to make in the same commit as this file:** README's
"About `.parallel()`" section currently claims "GIL-bound on the standard
build... offers no real speedup for CPU-bound work" without qualification.
That's confirmed true here. It also needs the free-threaded row above — which
it already states — but should not be read as "any CPU-bound `.parallel()`
call speeds up on 3.14t"; it needs enough elements to clear the `n=200`-style
single-batch cliff first. Worth a footnote if the section gets touched again.

## Batch-growth curve: one-step jump vs. Java-style increment

Design.md decision 1's addendum asks whether a smoother, incremental growth
rule (Java's `IteratorSpliterator`: +1024 per split) would be better than the
current single jump from `_FIRST_BATCH_SIZE` (4) straight to `BATCH_SIZE`
(1024) after round 1. Tested by monkeypatching
`_fork_join_ordered_batches()`'s growth line to `size = min(size +
_FIRST_BATCH_SIZE, BATCH_SIZE)` (a Java-shaped +4/round increment) against
the shipped one-step jump, on the cheap-mapper draining case (`n=8192`,
`collect(to_list())` — the pipeline fully drains, so the "memory held
resident" cost the addendum worried about doesn't apply; this isolates the
*dispatch-count* cost instead):

| growth rule | wall time (median) | batch dispatches (median) |
|---|---:|---:|
| current: one-step jump (4 → 1024) | 87.62ms | 12 |
| incremental: +4/round, capped at 1024 | 175.77ms | 126 |

**The one-step jump is the right call, confirmed rather than merely assumed.**
An incremental rule multiplies the number of `asyncio.to_thread` dispatches by
~10x for the same source, and each dispatch has real fixed overhead (thread
handoff, a fresh event loop per `_run_batch_sync()` call) — so a smoother
curve makes exactly the regression this section is about *worse*, not better.
Java's incremental growth exists to bound *per-split* memory under a
recursive fork-join pool that doesn't apply here (this design dispatches flat
batches, not recursive splits), so there was no correctness reason to copy it
either. Design.md's "for 7.2, not decided here" note is resolved: keep the
one-step jump.

## Reproduction

Scripts are not checked in (ad hoc, run against a `git worktree` at `a872f25`
plus the working tree); the shape is: `Stream.of(vals).parallel().map(mapper)
.collect(to_list())` timed with `time.perf_counter()`, `statistics.median`
over repeated in-process trials, run once under
`uv run --python /usr/local/bin/python3.14` (GIL build) and once under
`uv run --python 3.14t` (free-threaded), after confirming the two are
actually different interpreters (`sys._is_gil_enabled()`) since `uv run
python`'s default resolution on this machine is misleading.
