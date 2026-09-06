+++
id = "ramp-batch-growth-geometrically"
title = "Ramp fork/join's batch growth instead of jumping to it"
bucket = "now"
rank = 1
filed = 2026-08-20
updated = 2026-09-06
gate = "dispatch count, not wall time — the draining case must not regress past the measured +7 dispatches on 102 at n=100000"

[refs]
changes = ["ramp-batch-growth-geometrically", "fork-join-executor-and-spliterator"]
specs = ["racing-encounter-order", "stream-find-first"]
files = ["src/snakestream/execution.py"]
+++

Split from **Bound speculation separately from read-ahead** (filed 2026-08-20)
on 2026-09-06, which is where the analysis below happened. That item's gate was
"benchmark against the existing fork/join harness"; the benchmark was run, and
it answered the sizing question the item deliberately left open. Scaffolded as
the change of the same name — proposal and design written, specs and tasks not.
Still queue work: nothing is implemented.

*The cliff.* Both fork/join call sites grow the batch size in one step, from
`_FIRST_BATCH_SIZE` (4) per worker straight to `BATCH_SIZE` (1024). Measured on
`.parallel().peek(fn).any_match(x == k)` over 100k, one extra element past the
first round costs 4096 chain invocations — 16 at `k=10`, 4112 at `k=17`. A
geometric ramp seeded at one element per worker replaces it.

*Two corrections to the item this was split from, both load-bearing.*

**Its "dead half" is only dead for `find_first()`.** That terminal demands
`ALWAYS`, splits at the chain end and is answered by round one, so its bound
really is round one's. `iterator()` declares `IF_ORDERED`, splits at the same
place, and runs the identical one-step jump on the ordered path: a consumer that
`break`s at element 20 runs the chain on 4106. Both call sites change, and this
is also what rules out the shape the old title implies — a
`TerminalSink.short_circuits()` declaration beside `can_partition()` and
`demand()` could not catch `iterator()`, because nothing in the pipeline knows a
caller's `break` is coming. One growth curve, read off behaviour, does what a
second bound cannot.

**`fork-join-executor-and-spliterator` task 7.2 did not settle this.** It
settled the rule it measured — a Java-style **arithmetic** +4/round, 126
dispatches against 12 at n=8192, ~2x worse wall time — and that verdict stands.
It does not generalise to "a smoother curve is worse". Arithmetic from 4 to 1024
takes 255 rounds to saturate, so it is still climbing when any realistic source
runs out and its dispatch count is O(n); geometric saturates in four refills and
costs a constant. Measured, GIL build, `WORKERS=4`:

| growth rule | waste @k=1 | @17 | @20 | dispatches n=8192 | n=100000 |
|---|---:|---:|---:|---:|---:|
| shipped, one-step 4 -> 1024 | 16 | 4078 | 4082 | 12 | 102 |
| arithmetic +4/round (7.2) | - | - | - | 126 | - |
| geometric x8, seed 1 | 4 | 35 | 59 | 20 | 109 |

*`_FIRST_BATCH_SIZE` has its measurement now, and the answer is to delete it.*
The old item noted 7.2 never measured the first-round value `4`, which
`execution.py` still calls "a starting point, not a measurement". Seeding at `1`
beat `4` on every waste column for +3 dispatches, and stops being a number at
all: "one element per worker" describes the first round rather than tuning it.

*Open when starting.* Wall time on the GIL build was too noisy to prove no
regression (n=8192 reps ranged 94-149ms under both rules), which is why the gate
above is dispatch count — the same metric 7.2's own findings argued from, for
the same reason. `find_first()`'s documented bound tightens from 16 to 4 and the
symbol `stream-find-first` names ceases to exist, so that spec needs a delta,
not a prose sweep.
