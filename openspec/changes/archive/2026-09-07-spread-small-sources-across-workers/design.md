## Context

See proposal.md - Why. Two constraints shape this design.

First, this change owns no mechanism. `ramp-batch-growth-geometrically` changes
the growth curve; `benchmark-findings.md` (task 7.2) already identified that
curve as the direct cause of the small-source cliff. What is left here is
turning a benchmark footnote into a stated guarantee, verifying it, and
retracting the documentation that tells callers to work around it.

Second, the property is easy to state and hard to test honestly. The
*observable* effect is a wall-clock speedup on 3.14t, and a wall-clock
assertion in the suite would be flaky on CI runners, build-dependent, and would
fail on the GIL leg for reasons that are correct rather than regressions. The
guarantee has to be written so that what it promises is what can be checked.

## Goals / Non-Goals

**Goals:**

- State distribution across workers as a requirement, at the level where it is
  deterministic.
- Retire the caveat from README and CLAUDE.md rather than soften it.

**Non-Goals:**

- Any change to `execution.py`. If this change needs one, the split between the
  two changes was drawn wrong.
- Promising a speedup. See decision 1.
- Guaranteeing that all `WORKERS` workers are occupied, or that batches are
  evenly sized. See decision 2.

## Decisions

### 1. The requirement is about distribution, not speed

"`.parallel()` is faster on a small source" is untestable in a unit suite and
false on the GIL build, where the executor is working exactly as designed. The
guarantee is instead: *a source with more elements than `WORKERS` is dispatched
across more than one worker.* That is a property of the executor's batching,
holds identically on both interpreter builds, and is deterministic.

The speedup is then a *consequence* on a build that can realise it, and belongs
in README prose with its measurement, exactly where the caveat being retired
lives now.

**Alternative considered: assert a speedup ratio on 3.14t, skipped on the GIL
leg.** Rejected — it makes the suite's green depend on runner contention, and
the CI free-threaded leg exists to check correctness under no GIL, not to be a
benchmark harness.

### 2. The threshold is `WORKERS`, not a batch size

The natural phrasing is "a source that spans more than one batch", but batch
size is precisely the thing this pair of changes makes vary over the run, and a
requirement written against it would need rewriting the next time the ramp is
retuned — which `racing-encounter-order` explicitly reserves the right to do.

Written against `WORKERS`, the requirement survives any ramp whose first round
is one element per worker, which is what `ramp-batch-growth-geometrically`
decision 3 fixes as the shape rather than as a number. It is also the weakest
true statement, which is the right strength for a guarantee: it does not
promise even distribution, nor that every worker is used, only that the source
is not funnelled into one.

### 3. Verified by counting threads, not by timing

`_run_batch_sync()` runs on the `asyncio.to_thread` worker; recording
`threading.get_ident()` per dispatch and asserting more than one distinct id
for a source larger than `WORKERS` tests the requirement directly.

Measured against the true pre-ramp shape (`_FIRST_BATCH_SIZE=4` seed, then a
one-step jump to `BATCH_SIZE`), this does **not** discriminate old from new:
round one alone already dispatches up to `WORKERS` batches concurrently via
`asyncio.gather`, regardless of the seed size, so a source with more than a
worker's-worth of elements touches more than one thread in round one under
both the old code and the new. The pre-ramp cliff was never zero
distribution — it was that almost all of a small source's *elements* landed
in a single worker's batch in round two, while the rest sat idle, which is a
work-concentration problem the thread-count test cannot see and, per
decision 2, is not what this requirement promises to guarantee anyway
(distribution, not balance). The "deliberately break it once" discipline task
4.3 of `fork-join-executor-and-spliterator` established was applied here and
came back negative: the test is correct for what the requirement actually
states, but it does not double as a regression guard for the pre-ramp cliff.
That guard is `ramp-batch-growth-geometrically`'s own concern, not this
change's; the wall-clock benchmark in section 3 is what actually demonstrates
the improvement here.

### 4. The README caveat is deleted, not softened

README currently asks the caller to reason about whether their source "spans
enough batches". Once distribution is guaranteed, that sentence is not merely
pessimistic, it is wrong, and leaving a hedged version behind preserves the
reasoning burden the change exists to remove. The measured n=200 and n=800
figures replace it. The 0.3.5 Migration entry's parenthetical
("with enough elements to spread across more than one worker's batch") goes for
the same reason; the rest of that entry — the cheap-callable dispatch
regression — is unaffected and stays.

## Risks / Trade-offs

- **The guarantee is weak enough to be nearly free, and could be read as
  saying more than it does** — a caller may take "spread across workers" to
  mean "N times faster on N cores". -> The requirement's own text says it is
  about distribution and that wall-clock benefit depends on the interpreter
  build; README carries the measured figures next to it.
- **The measured figures (1.40x-1.52x at n=200) are below the ~2x that
  `benchmark-findings.md` reports for large sources**, so README will carry two
  different speedup numbers. -> That is honest and is the point: small sources
  improve from *slower than sequential* to meaningfully faster, without
  reaching the large-source figure. Both are stated with their n.
  > **Note (2026-09-07, superseded):** this machine's own measurement came in
  > higher — 2.01x-2.06x at n=200 — see `benchmark-findings.md`. The stated
  > figures are from a different machine (the proposal's own harness); the
  > qualitative point stands regardless of which machine's absolute numbers
  > are read.
- **This change is inert, and a green suite proves nothing, if it lands
  first.** -> Sequencing is stated in the proposal's Impact and in the Migration
  Plan below; the new test fails before the ramp, which makes an
  out-of-order landing loud rather than silent.
  > **Note (2026-09-07, falsified during implementation):** task 2.3 found
  > this does not hold. The thread-identity test passes under both the old
  > and new code for any source bigger than `WORKERS`, since round one alone
  > already dispatches to more than one worker regardless of the ramp — see
  > decision 3's revision, above. An out-of-order landing would be silent, not
  > loud; the wall-clock benchmark is the thing that would actually catch it.
- **Thread-identity assertions can be fragile if the executor ever pools or
  reuses in a way that collapses ids.** -> `asyncio.to_thread` uses the default
  executor's pool, whose threads persist; distinct *concurrent* batches get
  distinct ids. The assertion is "more than one distinct id", which a pool
  satisfies as long as work actually overlaps — which is the property under
  test.

## Migration Plan

Land after `ramp-batch-growth-geometrically`. No code changes and no API
changes, so nothing to roll back but documentation and one test.

## Open Questions

None.
