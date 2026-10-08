+++
id = "bound-in-flight-work-per-worker"
title = "The read-ahead constant is renamed, and its export declined (`bound-in-flight-work-per-worker`)"
filed = 2026-09-01
closed = 2026-09-01
outcome = "shipped"
shipped_as = "bound-in-flight-work-per-worker"
+++

**`bound-in-flight-work-per-worker`** (2026-09-01) — item 3, the last of the
four, and **it closed the other way from how the item said it would**. The
item read "its answer flipped to 'export it'"; this change renames the
constant and declines the export.

**The correction is that the obligation the item cited was already
discharged.** Item 3 argued that `_READ_AHEAD` had become public because it
bounds something a caller can count — how many times a mapper runs under a
parallel `find_first()` — and so "an observable effect a spec has to state".
The spec already stated it. `collapse-find-first-onto-barrier` wrote
`stream-find-first`'s "find_first() may invoke a chain's callables more than
once" in the same change that created the behaviour, **including both
regimes** — the worker count under uniform latency, the window otherwise.
Item 3 was written as if that requirement did not exist. Observable is not
the same as public: `find_any()`'s choice of element is observable and
spec'd, and nothing about it is exported.

**What shipped instead of an export.** `_READ_AHEAD` became
`_IN_FLIGHT_PER_WORKER = 4` plus `_in_flight(workers)`, so the bound scales
with the branch count — the tuning curve knees at *one slot per worker*, a
fact the old comment recorded and then contradicted by hardcoding 16. The
effective bound at the default worker count is unchanged (4 × 4 = 16) and no
behaviour a caller can observe changed, so there is **no migration-log
entry**; that absence is a claim, not an oversight. `_Window` now takes its
size at construction rather than reading a module global on every pull, which
is what makes "fixed for the duration of a run" true in the code.

**The rename stopped at the code, and that is the second correction.** The
item wanted the name to cover all three things the constant bounds and
guessed "the window" might be as close as it gets. But the *requirement* is
about elements pulled but not released, which **is** read-ahead, accurately;
what bounds three things is the constant. So `racing-encounter-order` keeps
the word and gained two clauses instead — the window scales with the branch
count, and its size is fixed for a run — plus a new requirement that the
bound is **not** public, naming `unordered()`/`sequential()` as the levers a
caller gets. That requirement is the change's actual product: it makes
retuning the value a measurement rather than a compatibility question, which
is what "revisit on a concrete report" never managed to say bindingly.

Queued a follow-up rather than folding it in — filed in **Now** → **Queued
changes** and moved to **Later** the same day, once it was clear the blocker
is a decision and not effort: one counter serves memory, latency and
speculation, and under a short-circuiting terminal it bounds the wrong one.
