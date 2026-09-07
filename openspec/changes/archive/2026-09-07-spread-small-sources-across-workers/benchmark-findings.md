# Benchmark findings — tasks 3.1-3.3

Measured 2026-09-07, working tree at this change (ramp-batch-growth-geometrically
already landed), on the same machine. CPU-bound mapper (4000-iteration inner
loop, same shape as `fork-join-executor-and-spliterator`'s own benchmark),
`Stream.of(vals).parallel().map(cpu_bound).collect(to_list())` vs the same
pipeline under `.sequential()`, timed with `time.perf_counter()`,
`statistics.median` over 5 in-process trials per (n, mode) pair. Two runs
recorded per build to show trial-to-trial spread.

## Free-threaded build (3.14.5, `gil=False`, `uv run --python 3.14t`)

| n | sequential (median) | parallel (median) | ratio (seq/par) |
|---:|---:|---:|---:|
| 200 | 68.49-69.58ms | 33.24-34.67ms | **2.01x-2.06x** |
| 800 | 280.62-283.09ms | 225.74-229.40ms | **1.22x-1.25x** |

Both runs' full trial sets:

- n=200, run 1: seq `[71.85, 68.14, 74.99, 69.58, 69.21]`, par `[34.82, 30.64, 34.67, 31.97, 37.70]`
- n=200, run 2: seq `[68.28, 68.49, 67.96, 69.98, 72.02]`, par `[32.21, 34.15, 42.90, 33.24, 31.25]`
- n=800, run 1: seq `[275.58, 284.40, 283.09, 286.46, 273.97]`, par `[218.45, 224.26, 229.63, 225.74, 230.81]`
- n=800, run 2: seq `[282.03, 275.45, 281.52, 280.62, 273.79]`, par `[219.27, 229.31, 229.40, 235.28, 245.03]`

Small sources now improve *more* at n=200 than at n=800 relative to
sequential, which is the ramp working as designed: at n=200 the round-1 seed
(one element per worker) already gets every worker started on real work
almost immediately, and the source is small enough that dispatch overhead
stays a small fraction of the total; at n=800 more of the run happens at
larger batch sizes, which is closer to the large-source steady state
(`fork-join-executor-and-spliterator`'s own n=4096/8192 figures, ~1.9x-2.0x)
but the per-batch-dispatch fixed cost is a proportionally larger share at
n=800 than at n=8192, keeping this ratio lower than the large-source figure.

Both figures are clean, reproducible improvements over `.sequential()` — the
proposal's `1.40x-1.52x`/`1.39x-1.67x` (a different machine, task 7.2's
original harness) and these numbers agree on the qualitative finding (small
sources now speed up rather than regress) even though the absolute ratios
differ by machine.

## GIL-enabled build (3.14.5, `gil=True`, `uv run --python /usr/local/bin/python3.14`)

| n | sequential (median) | parallel (median) | ratio (seq/par) |
|---:|---:|---:|---:|
| 200 | 109.35ms | 109.17ms | 1.00x |
| 800 | 420.42ms | 430.15ms | 0.98x |

No change from before the ramp, as expected: the GIL serializes Python
bytecode across `.parallel()`'s worker threads on this build regardless of how
the batches are distributed, so distribution alone cannot produce a wall-clock
win here. This is not a regression — `parallel-worker-utilisation`'s
Requirement 3 states the guarantee is distribution, not speedup, precisely
because of this build difference.

## What flipped, mechanically

Before `ramp-batch-growth-geometrically`, a 200-element source at
`WORKERS=4`, `_FIRST_BATCH_SIZE=4` covered 16 elements in round 1, then jumped
straight to `BATCH_SIZE=1024` in round 2 — draining the remaining 184
elements into a single worker's batch while the other three sat idle. The
geometric ramp (seed 1, x8 per refill) means round 2 covers only 8 elements
per worker (32 total), round 3 covers 64 per worker (256, more than enough
to finish a 200-element source) — so a 200-element source is fully consumed
within 3-4 rounds, each of which still dispatches to as many workers as have
work, rather than one round dumping most of the source onto one thread.

Note (task 2.3, recorded per design.md decision 3's revision): this
mechanical difference does **not** show up as a "how many distinct threads
ran a batch" count — round 1 alone already spans multiple workers under both
the old and new code for any source bigger than `WORKERS`, so a thread-count
test cannot discriminate old from new. What changed is how much of the
source's *work* each thread gets, which only shows up in wall-clock terms —
these figures, not the distribution test, are the evidence for the
improvement.

## Reproduction

Script: `bench_small_source.py` (not checked in — ad hoc, scratchpad only).
Shape: `Stream.of(vals).parallel().map(cpu_bound).collect(to_list())` timed
with `time.perf_counter()`, `statistics.median` over 5 trials, run once under
`uv run --python 3.14t` (free-threaded) and once under
`uv run --python /usr/local/bin/python3.14` (GIL-enabled), confirming the
build via `sys._is_gil_enabled()` printed at the top of each run — following
`fork-join-executor-and-spliterator`'s own note that `uv run python`'s default
resolution on this machine is not reliably one build or the other.

```python
def cpu_bound(x: int) -> int:
    total = x
    for _ in range(4000):
        total = (total * 1103515245 + 12345) & 0x7FFFFFFF
    return total
```
