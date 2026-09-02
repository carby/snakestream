## Context

See proposal.md — Why. The shape today, in `_guarded()`'s windowed arm:

```
    while True:                         <-- retry loop
        while window.full():            <-- no slot: broadcast wait
            window.event.clear()
            await window.event.wait()
        async with lock:
            if window.full():           <-- slot may be gone again
                continue                    (barged) -> retry
            item = await anext(source)
            index = window.assigned
            window.assigned += 1
        break
    yield index, item
```

`_Window` is shared between `_guarded()` and `_release_in_order()`, and its
`released` field does two jobs: it is the flow-control counter (`full()` reads
`assigned - released`) and it is the reorder cursor `_releasable()` walks. Only
the first job is in scope here.

The bound is enforced in `_guarded()` because that is the last point at which
pull order still *is* encounter order and the only place a pull happens — see
`2026-08-26-order-stateful-ops-under-racing` design.md §4, which chose the
`Event` and reasoned about wait-outside-the-lock and deadlock-freedom without
ever weighing a slot-holding primitive against it.

## Goals / Non-Goals

**Goals:**

- One loop level and no post-lock re-check in `_guarded()`'s windowed arm.
- The barging window closed rather than compensated for.
- No measurable per-element cost on the ordered-delivery path.

**Non-Goals:**

- Changing the bound's value, its scaling, or when it is fixed — all three are
  `racing-encounter-order` requirements and all three are preserved.
- Touching `_guarded()`'s unwindowed arm, which runs for every pipeline that
  needs no barrier and must stay exactly what it was.
- The separate question of bounding *speculation* under a short-circuiting
  terminal, which is a behaviour change parked in roadmap **Later**. This
  change alters no behaviour at all.

## Decisions

### 1. A synchronous `take()` on `_Window`, not `asyncio.Semaphore`

`asyncio.Semaphore` is exactly the missing primitive by contract — N slots,
atomically claimed, waited on outside any lock — and it was this change's first
candidate. It is declined on measurement.

Both variants were installed onto the live `snakestream.execution` module
rather than loaded as a second copy, so one `OrderDemand` enum exists in the
process and `_split_point()`'s `is` comparisons keep working — the trap
recorded in `extract-racing-task-lifecycle`. Python 3.14.5, 20,000 elements,
`map(x + 1)`, 4 workers, draining into `_CountSink`, 10 interleaved rounds per
run, three independent runs. µs/element, min / median, against the shipped
baseline:

| variant | order-blind (no window) | ordered delivery (window) |
|---|---|---|
| `asyncio.Semaphore` | −1.5% / +0.6%, −0.2% / −1.5%, −1.3% / −0.6% | **+5.7% / +7.3%, +3.9% / +6.0%, +6.4% / +5.6%** |
| `take()` | +2.5% / +1.6%, +1.2% / +1.1%, −0.8% / −0.8% | **+1.2% / +0.3%, +0.4% / +0.9%, −0.0% / −1.2%** |

The semaphore's charge is positive in all six windowed statistics and absent
from the order-blind path it does not touch — which is what a per-element cost
looks like and what run-to-run drift does not. The cause is structural:
`Semaphore.acquire()` is an `async def`, so `await sem.acquire()` allocates a
coroutine object and frame per pull even though CPython 3.14's fast path
(`if not self.locked(): self._value -= 1; return True`) never suspends. Same
family of finding as `add-callsite-dispatch`, `Sequential.value()`'s existence
and the rejected `merge()` generator: **on a per-element path here the
comparison is abstraction against free, not abstraction against cheaper
abstraction.**

`take()` keeps the semaphore's contract and pays none of it. It is atomic for
the reason `_LimitSink.accept()`'s reserve-before-push is atomic and says so:
it contains no `await`, so nothing can run between its check and its increment.
That is a property of the code, not of a lock, and it is why the post-lock
re-check has nothing left to guard.

**This library has made this exact move once before, on the counter next
door.** The change that introduced `_guarded()` at all — the `ParallelStream`
fix for `anext(): asynchronous generator is already running`, roadmap
**Done** — surfaced a latent race in `_LimitOp`: a check-then-pull-then-
increment against the shared size counter stopped being atomic once the pull
could genuinely cede control, and multiple branches passed the check before
any incremented. It was fixed by reserving the slot *before* the pull, "so the
check-and-reserve step has no `await` between them and stays atomic across
racing branches" — the words `_LimitSink.accept()`'s comment still carries.
The read-ahead window is the same counter shape under the same racing
branches, and it was given the weaker primitive. This change applies the
answer that was already found here.

Straddling zero on the windowed path across three runs, and inside the noise
the untouched order-blind path shows, the `+10%` ns/element gate is met with
room to spare.

### 2. `outstanding` as a third counter, rather than reusing `assigned - released`

`full()` derived occupancy from the two counters the barrier already keeps.
A slot claimed by `take()` exists *before* an index is assigned, so occupancy
and `assigned - released` are no longer the same number and cannot share a
field. `assigned` stays the index counter; `released` stays the reorder cursor
that `_releasable()` walks; `outstanding` is occupancy and nothing else. Three
fields each with one job, where two had three between them.

The alternative — claiming the slot under the lock, where the index is
assigned — is what the code does today, and is precisely what forces the wait
to happen before the lock and therefore the re-check after it.

### 3. Claiming early tightens the bound, and that is the safe direction

Between `take()` and the assignment a branch holds a slot with no index, so
occupancy now counts a pull that is about to happen as well as every element
pulled and not released. The bound is therefore conservative: never looser than
before, occasionally tighter by the number of branches mid-pull. Every
requirement and every test asserts an upper bound
(`pulled_before_first_release <= _in_flight(...)`), so tightening cannot break
one.

### 4. The exhaustion path gives its slot back

A branch whose `anext()` raises `StopAsyncIteration` produces no group, so
nothing downstream will ever release the slot it claimed. Left leaking it is
not a deadlock — the merge drains `pending`, waiting branches wake, and each
exits the same way — but the window would shrink by up to one slot per branch
during teardown for no reason. `give_back()` is the honest fix and is one line
on a path that runs once per branch per pipeline.

This is genuinely new bookkeeping rather than preserved behaviour: today no
slot is claimed on that path at all, because the claim and the assignment are
the same act.

## Risks / Trade-offs

- **A future edit inserts an `await` into `take()`, silently reopening the
  barging window** → the atomicity is stated in `take()`'s own docstring as the
  reason it has no `await`, in the same words `_LimitSink.accept()` uses for
  the same property. `test_branches_contending_for_the_last_window_slot_still_
  pull_in_order` keeps its value as the regression gate: it drives a window of
  one against a source that really suspends mid-pull, which is the shape that
  fails if the take stops being atomic.
- **Three counters are easier to desynchronise than two** → `outstanding` is
  incremented in exactly one place (`take()`) and decremented in exactly two
  (`release_one()`, `give_back()`), all three on `_Window` itself; no caller
  touches it.
- **The measured margin is small enough to be reversed by an unrelated change
  on this path** → the figures are recorded per variant and per run above, and
  the harness is a scratch script rather than a committed benchmark, so a later
  re-measurement compares like with like by reconstructing it from this table's
  stated parameters.

## Migration Plan

None applies. No public name, signature, import or observable behaviour
changes, so there is nothing to migrate and no README migration-log entry —
that absence is a claim, not an oversight. Rollback is reverting the commit.
