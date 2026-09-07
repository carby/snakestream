## Context

See proposal.md - Why. The constraint that shapes everything here is a prior
measurement: `fork-join-executor-and-spliterator` task 7.2 tested a smoother
growth curve and rejected it, and this change reopens that verdict. Any design
that does not confront the earlier measurement head-on is not credible, so the
first decision below is about why the two results do not contradict each other.

Two call sites grow the batch size, and they are not symmetric today only by
accident. `_fork_join_ordered_batches()` escalates after a full round of
`workers` batches and only when the round was full;
`_fork_join_unordered_batches()` escalates after the first *completed batch*.
Both jump 4 -> 1024 in one step.

## Goals / Non-Goals

**Goals:**

- One growth rule, expressible in a sentence, that needs no second number and
  no knowledge of whether the consumer will short-circuit.
- Delete `_FIRST_BATCH_SIZE` rather than measure it.

**Non-Goals:**

- Introducing a speculation bound *separate* from the read-ahead bound. The
  roadmap row that motivated this work is titled "Bound speculation separately
  from read-ahead", implying a second number or a new declaration on
  `TerminalSink`. This design rejects that shape; see decision 2.
- Changing `WORKERS` or `BATCH_SIZE`.
- Retiring the free-threaded small-source caveat, which this ramp also fixes.
  Sequenced separately as `spread-small-sources-across-workers`.

## Decisions

### 1. Geometric growth, not the arithmetic growth task 7.2 rejected

Task 7.2 measured `size = min(size + _FIRST_BATCH_SIZE, BATCH_SIZE)` — Java's
`IteratorSpliterator` shape — and found 126 batch dispatches against the
shipped 12 at n=8192, with ~2x worse wall time. That verdict is correct and is
not being overturned. It simply does not transfer.

An arithmetic ramp from 4 to 1024 in steps of 4 takes 255 rounds to saturate,
so for any realistic source it is still climbing when the source runs out: its
dispatch count is O(n) in the source length. A geometric ramp saturates in
`log_8(1024) = 3.3` rounds — after four refills it *is* the shipped rule. Its
extra dispatch count is therefore additive and bounded by the number of rounds
below the cap, independent of source length:

| rule | n=200 | n=8192 | n=100000 |
|---|---:|---:|---:|
| shipped, one-step | 5 | 12 | 102 |
| arithmetic +4/round (rejected) | - | 126 | - |
| geometric x8, seed 1 | - | 20 | 109 |

At n=100000 the ramp costs +7 dispatches on 102 — a fixed toll, paid once, that
does not grow. That is the whole argument, and it is why "a smoother curve
makes the regression worse" is true of the rule 7.2 tested and false of this
one.

**Alternative considered: keep the one-step jump and add a cap that applies
only under a short-circuiting terminal.** Rejected under decision 2.

### 2. One curve, not two numbers — the executor never learns the consumer's intent

The obvious reading of the roadmap row is that the executor should behave
differently when its consumer may short-circuit: a `TerminalSink.short_circuits()`
declaration alongside the existing `can_partition()` and `demand()`, feeding a
smaller cap.

That shape cannot work, and the reason is a measurement, not a taste argument.
The same cliff appears on the ordered path through `iterator()`, where there is
no terminal at all — the consumer is a `break` in the caller's own `async for`:

```
async for _ in stream.parallel().peek(fn).iterator():   # break at element 20
    -> chain ran on 4106 elements
```

No declaration on any sink would have caught that, because nothing in the
pipeline knows the loop is about to end. A ramp needs no such knowledge: it is
small when little has been consumed and large once a lot has, which is the same
signal, read off behaviour instead of off a promise.

This also revises the roadmap row's own framing. It classifies the ordered path
as the "dead half" on the grounds that `find_first()` demands `ALWAYS`, splits
at the chain end and is answered by round one. That is true of `find_first()`
and not of `iterator()`, which declares `IF_ORDERED`, splits at the same place,
and runs the identical one-step jump at the ordered call site. Both call sites
change here.

### 3. Seed the ramp at 1 and delete `_FIRST_BATCH_SIZE`

The constant's comment concedes it is "a starting point, not a measurement",
and 7.2 measured the growth rule without ever measuring the seed. Measured now:

| seed (x8 ramp) | waste @k=1 | @17 | @20 | dispatches n=8192 |
|---|---:|---:|---:|---:|
| 4 | 16 | 142 | 80 | 17 |
| 2 | 8 | 71 | 96 | 16 |
| 1 | 4 | 35 | 59 | 20 |

> **2026-09-07:** Task 3.2 (`ramp-batch-growth-geometrically`'s tasks.md)
> reproduced this table against the landed code, not the prototype these
> figures came from. `@k=1` reproduces closely (3-4 across trials). `@17` and
> `@20` do **not** reproduce these exact figures and are run-to-run noisy on
> the landed code — three trials measured (k=17, k=20): (36, 204), (92, 148),
> (38, 36) — because the unordered path's waste depends on real concurrent
> completion order (`asyncio.wait(FIRST_COMPLETED)`), which this table's
> figures apparently did not exhibit at the same variance. The seed-1-vs-4
> *comparison* this table argues for is unaffected — same order of magnitude,
> nowhere near the seed-4 column, let alone the old code's ~4096 — but do not
> read `35`/`59` as reproducible measurements of the landed code.

Seed 1 is strictly better on every waste column for +3 dispatches. More
importantly it stops being a *number*: "one element per worker" is a
description of the first round, not a tuning parameter, so there is nothing
left to name or to justify. The `_FIRST_BATCH_SIZE` block — 12 lines of comment
explaining a double-counting bug in the constant's own units — goes with it.

The interaction with `_pull_round()`'s multiply-by-`workers` that caused that
bug (16 meant as a total, read as per-worker, giving 64) cannot recur: 1 is
1 in either reading.

**Alternative considered: seed 4, keep the constant.** It measures worse on the
thing this change exists to fix, and preserves a symbol whose only defence was
that nobody had measured it.

### 4. x8, not x4

Both fix the cliff. x8 costs fewer dispatches (16 vs 22 at n=8192 from seed 4)
and saturates in 4 refills instead of 5; x4 cuts speculative waste roughly
twice as hard. Neither difference is large, and the choice is the user's, made
on the ground that dispatch overhead is the measured regression this executor
already carries (README's 0.3.5 Migration entry) and is the cost worth
protecting. x8 it is; the ratio is a constant free to change on measurement
under `racing-encounter-order`'s "the bound may be retuned" requirement.

### 5. Both call sites get the same rule

The ordered and unordered paths escalate on different events (a full round vs.
the first completed batch) and that difference is deliberate — it is what makes
the order-blind path yield as soon as any batch returns. The *growth rule*
sitting on top of it has no such reason to differ, and a divergence would need
its own explanation in a file that already carries a lot of them. Same
expression, same seed, both places.

## Risks / Trade-offs

- **The ramp's toll is real, if small, on a draining pipeline that never
  short-circuits** — the case README's 0.3.5 Migration entry already flags as
  regressed. Measured at +7 dispatches on 102 at n=100000, with wall time
  unchanged within noise. -> Accepted, and recorded with its measurement rather
  than asserted; the alternative preserves a 257x speculation cliff to save a
  constant number of thread dispatches.
- **Wall-time measurements on the GIL build were too noisy to prove no
  regression** (n=8192 reps ranged 94-149ms under both rules). -> Dispatch
  count is the metric this design argues from, as task 7.2's own findings did
  for the same reason. A wall-time claim should not be made from these numbers.
- **`find_first()`'s bound tightens from 16 to 4**, and callers reading the
  spec may have relied on the looser figure. -> The requirement is that the
  count is *bounded*, not what it is bounded to, and
  `racing-encounter-order`'s "The bound may be retuned without a breaking
  change" requirement covers exactly this. A tightening cannot break a caller
  who was correct under the old bound.
- **A test imports `_FIRST_BATCH_SIZE` by name** and will fail to import. ->
  Intended; the spec delta and the test change are the same edit, and
  `tests/test_package_exports.py` already asserts which read-ahead names exist.

## Migration Plan

Land `ramp-batch-growth-geometrically` first; `spread-small-sources-across-workers`
depends on it and is inert before it. No caller-visible API changes, so no
README Migration entry is owed by *this* change — the behaviour that changes is
a bound the specs declare retunable, and the observable results are identical.
Rollback is reverting two expressions and restoring one constant.

## Open Questions

None. The seed, the ratio, and the two-call-site scope are all decided above
with measurements; the remaining unknowns (should `WORKERS` or `BATCH_SIZE`
themselves move?) are out of scope and change neither the specs nor the tasks.
