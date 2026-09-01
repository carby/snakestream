## Context

See proposal.md — **Why**. Two facts about the current code shape the approach.

`_READ_AHEAD` is read *live*: `_Window.full()` consults the module global on
every pull, so a rebind takes effect part-way through a running pipeline. That
is not a designed capability, it is what a module global reached from a hot
method does by default, and one test depends on it (monkeypatching before the
pipeline is built, which happens to also cover during).

`_Window()` is constructed in exactly one place — inside `race_through()`, at
the split branch — and `workers` is already in scope there. Nothing else needs
to learn a new parameter for the bound to become derived, which is why this
change does not touch `Racing`, `Executor`, or any signature outside
`execution.py`'s private surface.

## Goals / Non-Goals

**Goals:**

- One site owns the derivation, and it is the site that already owns `workers`.
- The name covers all three things the bound governs, not the one it used to.
- The bound's non-public status is a written requirement rather than a comment,
  so retuning it later is a measurement, not a compatibility decision.

**Non-Goals:**

- Any public symbol, in either direction. Nothing is exported, and `PROCESSES`
  is not made to work differently (see the trade-off below).
- Changing the effective bound at the default worker count. `4 * 4 = 16` is the
  value today and after.
- Reducing the speculative work a short-circuiting terminal performs. That is
  the follow-up, and it is behaviour; this change is not.
- Any change to `_split_point()`, `_release_in_order()`, or `_run_ordered_tail()`.

## Decisions

**A function, `_in_flight(workers)`, not a bare derived constant.**
`_IN_FLIGHT_PER_WORKER * workers` inlined at the call site would work for
production and break the tests: one test needs a window of exactly **1** to
reproduce the contention it covers (two branches racing for the last slot), and
no integer ratio produces 1 at four workers. A function gives the tests a single
seam to patch and gives the bound's assertions a single expression to read.
Alternative considered: keep a module global and multiply at construction —
rejected, because it leaves two names for one quantity and the tests still have
nothing clean to patch.

**The size moves onto `_Window`, fixed at construction.**
`_Window.full()` compares against `self.size` instead of a module global. This
is what makes "fixed for the duration of a run" true in the code rather than
only in the spec, and it removes a global read from the per-pull path. The test
that shrinks the window patches `_in_flight` *before* the pipeline is built,
which is the honest ordering anyway.

**Per-worker, not absolute.** The measurement recorded in the constant's comment
knees at the worker count and the chosen value is four times it. Encoding the
ratio says what was measured; encoding 16 says what was measured at four
workers and silently stops being right at any other count. It also makes the
comment's table expressible on its true axis.

**The spec keeps "read-ahead"; the code does not.** The requirement governs
elements pulled but not released, which *is* read-ahead. The constant governs
that plus latency plus speculative invocation, which is not. Renaming the
requirement to match the constant would make the spec less accurate to buy
symmetry with an internal name the spec is not supposed to know about.
Alternative considered: rename both to "in-flight" — rejected on that ground,
and because a `RENAMED` delta has no precedent in this repo's archive and buys
nothing here.

**Nothing changes about `PROCESSES`.** It is snapshotted into `RACING` at import
and so is not actually tunable despite the spec calling it "the tunable worker
count" — a real inconsistency, and out of scope. Recorded here so the next
reader does not mistake it for something this change introduced or overlooked.

## Risks / Trade-offs

- **The window's value is now indirect: `4` and `PROCESSES` rather than `16`.**
  A reader asking "how many groups can be resident?" has to multiply. →
  `_in_flight()`'s docstring states the default product explicitly, and the
  measurement table is re-expressed per worker so the ratio is the thing the
  evidence is actually about.

- **Raising `PROCESSES` now raises memory quadratically-ish** — more branches,
  each permitted proportionally more in flight. → This is the intended
  behaviour and matches what the knee measurement says, but it is a real change
  in what a hypothetical `PROCESSES` bump would cost, so the spec states the
  scaling rather than leaving it implicit. Nobody can trip it today, since
  `PROCESSES` is inert after import.

- **A future change wanting a per-pipeline window has to undo the derivation.**
  → Cheap: `_Window` already takes its size as an argument, so the value's
  *source* is the only thing that would move.

- **Writing "not public" into a spec is a commitment that has to be revisited if
  a real report arrives.** → That is the intent. The requirement names the two
  levers a caller does have, so a report has to argue past them rather than
  past silence.

## Migration Plan

None. No public symbol changes, no behaviour a caller can observe changes, and
the effective bound at the default worker count is identical. Deliberately **no
README migration-log entry** — the standing rule is that every break gets one,
and the absence here is a claim that there is no break, stated so it does not
read as an omission.

Rollback is a revert; nothing is persisted and no on-disk format is involved.

## Follow-up: bound speculation separately from read-ahead

Not part of this change. Filed in `roadmap.md` under **Later**, because its
blocker is a decision rather than effort — see below. Recorded here because this
change is the one that makes the case legible.

One counter serves three purposes, and under a short-circuiting terminal it is
bounding the wrong one. `.peek(fn).find_first()` fills the whole window behind
an outstanding index 0 and discards everything but the winner. The window exists
to bound memory and latency; speculation is a side effect of reusing its
counter.

```
  today                              follow-up
  -----                              ---------
  branches fill the window           branches do not start new groups
  behind index 0 while it is         past an outstanding candidate the
  outstanding                        terminal could settle on
        |                                  |
        v                                  v
  a window's worth of wasted          in-flight work bounded near the
  work in the slow-head case          worker count, which is already the
                                      usual regime
```

Why it is a separate change, and a **Later** one rather than a queued one:
`race_through()` does not know its terminal can short-circuit. That information lives in the sink's
`cancellation_requested()`, downstream of the window, so a signal path has to
exist before the policy can. And the policy is a trade — branches that stop
pulling idle instead — so it needs its own measurement.

The figures to beat are already recorded in
`collapse-find-first-onto-barrier`: `filter`/`flat_map` at 3.11x/3.21x wasted
invocations, `map` at 0.96x. It would help the shapes where speculation runs *in
front of* the element that matters and do nothing for the shape where it runs
alongside — which is itself worth knowing before anyone starts.
