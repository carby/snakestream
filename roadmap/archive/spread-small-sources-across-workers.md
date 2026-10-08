+++
id = "spread-small-sources-across-workers"
title = "A small source should reach more than one worker"
filed = 2026-09-06
closed = 2026-09-07
outcome = "shipped"
shipped_as = "spread-small-sources-across-workers"
+++

**A small source should reach more than one worker** (closed 2026-09-07;
filed 2026-09-06, split from "Ramp fork/join's batch growth instead of
jumping to it" once that item's benchmark identified the cause). Shipped as
`spread-small-sources-across-workers`; no mechanism of its own — the ramp it
is sequenced after is what fixed the underlying cliff.

A new capability, `parallel-worker-utilisation`, states for the first time
that a source with more elements than `WORKERS` is dispatched across more
than one worker, and that this holds from the very first elements, not only
once the batch-size ramp has climbed. It deliberately promises distribution,
not speedup or balance — a wall-clock claim is untestable in a unit suite and
false on the GIL build, where the executor works exactly as designed either
way.

**The item's own gate — "verified by counting distinct worker threads, never
by timing" — turned out to be wrong, and was corrected in design.md rather
than worked around.** Monkeypatching the true pre-ramp shape
(`_FIRST_BATCH_SIZE=4` seed, then a one-step jump to `BATCH_SIZE`) and
re-running the thread-identity test showed it passing under the *old* code
too: round one alone already dispatches up to `WORKERS` concurrent batches
via `asyncio.gather` regardless of seed size, so a source bigger than
`WORKERS` touches more than one thread in round one either way. The pre-ramp
cliff was never "only one thread ever runs" — it was that a small source's
*work* mostly landed in a single worker's round-two batch while the others
sat idle, which a thread-count test cannot see and which Requirement 3
(distribution, not balance) does not promise to catch. The thread-identity
tests still verify the stated requirement correctly; they just do not double
as the regression guard the item assumed. That guard is the wall-clock
benchmark instead.

Measured on this machine (3.14t, `gil=False`), CPU-bound mapper, against the
same source under `.sequential()`: n=200 improved from a small deficit
(0.93x-0.99x) before the ramp to **2.01x-2.06x** after it; n=800 from
0.95x-1.04x to **1.22x-1.25x**. (The proposal's own figures, taken on a
different machine, were 1.40x-1.52x and 1.39x-1.67x respectively — different
absolute numbers, same qualitative finding.) The GIL-enabled build showed no
change either way (~1.00x/0.98x), as expected: distribution alone cannot
produce a wall-clock win where bytecode execution is serialized regardless of
which thread holds it.

README's "About `.parallel()`" and its 0.3.5 Migration entry, and `CLAUDE.md`'s
"Sequential vs. parallel execution", each lost the "spans enough batches to
spread across workers" / "can land entirely in one worker's batch" caveat —
deleted, not softened, since once distribution is guaranteed the caveat is
wrong rather than merely pessimistic.
