+++
id = "spread-small-sources-across-workers"
title = "A small source should reach more than one worker"
bucket = "now"
rank = 1
filed = 2026-09-06
gate = "sequenced after ramp-batch-growth-geometrically, and verified by counting distinct worker threads — never by timing"

[refs]
changes = ["spread-small-sources-across-workers", "fork-join-executor-and-spliterator"]
files = ["src/snakestream/execution.py", "README.md", "CLAUDE.md"]
+++

Surfaced 2026-09-06 while benchmarking `ramp-batch-growth-geometrically`
(closed 2026-09-07; see [`decisions.md`](../decisions.md)), and split out from
the same parent item. Scaffolded as the change of the same name — proposal and
design written, specs and tasks not. Still queue work.

`.parallel()` is documented as *slower than `.sequential()`* for CPU-bound work
on a small source, even on the free-threaded build where real parallelism is
available. README's "About `.parallel()`" asks the caller to reason about
whether their source "spans enough batches to spread across workers", and
`fork-join-executor-and-spliterator`'s own `benchmark-findings.md` names the
cause: round two's jump straight to `BATCH_SIZE` drains the whole remainder into
a *single* worker's batch, because `batch()` pulls up to 1024 from one shared
iterator before the next worker gets a turn. That file closes with "The growth
curve's shape controls this cliff directly."

So the mechanism is the ramp, and this item owns none of its own — it is the
guarantee, the verification, and the retraction of the caveat. Measured on 3.14t
(`gil=False`), CPU-bound mapper, against the same source under `.sequential()`:

| n | shipped | ramped |
|---:|---:|---:|
| 200 | 0.93x-0.99x (slower) | **1.40x-1.52x** |
| 800 | 0.95x-1.04x | **1.39x-1.67x** |

*Why it is not a bullet inside the ramp item.* What wants stating is
distribution — a source with more elements than `WORKERS` reaches more than one
worker — which is a different claim from a read-ahead bound, holds identically
on both interpreter builds, and no capability asserts today.
`free-threaded-support` is about CI legs and module-level state;
`stream-execution-model` says execution mode is a value and what a terminal
declares. Neither covers it, so this needs a new capability rather than a delta.

*Open when starting.* The guarantee has to be written at the level that can be
checked: a wall-clock assertion would be flaky on CI runners and would fail the
GIL leg for reasons that are correct. Counting distinct `threading.get_ident()`
values per dispatch tests distribution directly, fails today on a 200-element
source, and passes after the ramp.
