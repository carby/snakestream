## Why

`.parallel()` is documented as *slower than `.sequential()`* for CPU-bound work
on a small source, even on the free-threaded build where real parallelism is
available. README's "About `.parallel()`" carries the caveat:

> a source small enough to fit in one worker's first couple of batches ... may
> see only one thread ever get real work, so the speedup shows up once the
> source spans enough batches to spread across workers

`benchmark-findings.md` (task 7.2) names the cause precisely: with
`_FIRST_BATCH_SIZE=4` and `WORKERS=4`, round one covers 16 elements, and round
two's jump straight to `BATCH_SIZE=1024` means the entire remainder is drained
into a *single* worker's batch, because `batch()` pulls up to 1024 from one
shared iterator before the next worker gets a turn. It closes: "The growth
curve's shape controls this cliff directly."

> **Note (superseded premise):** `ramp-batch-growth-geometrically` deleted
> `_FIRST_BATCH_SIZE` and replaced the one-step 4 -> 1024 jump with a
> geometric ramp (seed 1 per worker, x8 per refill, capped at `BATCH_SIZE`).
> Round one now covers `WORKERS` elements (4 at the defaults), not 16, and
> there is no longer a single jump straight to `BATCH_SIZE` — the climb passes
> through several rounds first. This change is sequenced after that one and is
> where the small-source cliff itself gets retired; its own measurements
> should be taken against the ramp, not against the one-step figures above.

`ramp-batch-growth-geometrically` changes that curve for a different reason —
bounding speculative work under a short-circuiting terminal. This change is
where the cliff itself is retired: measured, verified as a behavioural
guarantee rather than a benchmark footnote, and removed from the caveats
callers are asked to reason about.

Measured on 3.14t (`gil=False`), CPU-bound mapper, against the same source
under `.sequential()`:

| n | shipped | with the ramp |
|---:|---:|---:|
| 200 | 0.93x - 0.99x (slower) | **1.40x - 1.52x** |
| 800 | 0.95x - 1.04x | **1.39x - 1.67x** |

## What Changes

- A behavioural guarantee is stated for the first time: a source with more
  elements than `WORKERS` reaches more than one worker. Today nothing promises
  this, and in fact it does not hold — a 200-element source runs on one thread.
  > **Note (2026-09-07, falsified during implementation):** task 2.3 found
  > this last claim wrong. Round one alone already dispatches to more than one
  > worker pre-ramp, for any source bigger than `WORKERS`. What did not hold
  > was that *most of the source's elements* reached more than one worker —
  > round two's one-step jump to `BATCH_SIZE` drained the remainder into a
  > single worker's batch. See design.md decision 3 and
  > `benchmark-findings.md`.
- README's "About `.parallel()`" loses the "once the source spans enough
  batches" qualifier and states the measured post-ramp behaviour instead.
- README's Migration entry for 0.3.5 loses its parenthetical "with enough
  elements to spread across more than one worker's batch".
- `CLAUDE.md`'s parallel-execution section loses the same caveat ("a small
  source can land entirely in one worker's batch and see no benefit").
- A benchmark on 3.14t records the new small-source figures, in the change, per
  the roadmap's convention that a performance claim carries its measurement.

No source change of its own: the mechanism is
`ramp-batch-growth-geometrically`'s ramp. This change is the guarantee, the
verification, and the retraction of the documented caveat.

## Capabilities

### New Capabilities

- `parallel-worker-utilisation`: how a parallel stream's source is distributed
  across workers — that a source large enough to occupy more than one worker
  does occupy more than one, that this holds regardless of where the ramp has
  reached, and that the guarantee is about distribution rather than about
  wall-clock speedup, which depends on the interpreter build.

### Modified Capabilities

None. `free-threaded-support` is about CI legs and module-level state, not
about how work is distributed, and `stream-execution-model` specifies that
execution mode is a value and what a terminal declares — neither states a
distribution property for this change to modify.

## Impact

- Depends on `ramp-batch-growth-geometrically`; has no effect before it lands
  and should be sequenced after it.
- `README.md` — "About `.parallel()`", and the 0.3.5 Migration entry.
- `CLAUDE.md` — "Sequential vs. parallel execution".
- New `openspec/specs/parallel-worker-utilisation/spec.md` via this change's
  delta.
- A new test asserting distribution, not timing: a timing assertion on a
  free-threaded speedup is exactly the flaky shape the branch-coverage gate and
  existing benchmark practice keep out of the suite. Counting *distinct worker
  threads* that ran a batch is deterministic and is what the guarantee actually
  says.
