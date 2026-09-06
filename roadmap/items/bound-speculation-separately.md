+++
id = "bound-speculation-separately"
title = "Bound speculation separately from read-ahead"
bucket = "now"
rank = 1
filed = 2026-08-20
updated = 2026-09-05
gate = "benchmark against the existing fork/join harness"

[refs]
changes = ["fork-join-executor-and-spliterator"]
specs = ["stream-execution-model", "racing-encounter-order"]
files = ["src/snakestream/execution.py"]
+++

One counter served three concerns — memory held by the reorder buffer, latency
behind a straggler, and how many elements a chain callable runs on under a
short-circuiting terminal. Filed in **Later**, then marked *"Moot as of
`fork-join-executor-and-spliterator` (2026-09-04)"*. **That verdict was wrong
and is withdrawn.** Half the row died with the racing executor; the other half
is live, and moved to **Now** on 2026-09-05 because nothing about it is
decision-blocked any more — the real-parallelism call it was parked behind is
resolved, and what remains is a benchmark against an existing harness.

*Dead half:* the row's own worked example, `.peek(fn).find_first()`.
`find_first()` demands `ALWAYS`, so it splits at the chain end, runs ordered,
and is answered by round one — bounded at `WORKERS * _FIRST_BATCH_SIZE` = 16
chain invocations, which is what the old window gave, now by a number that
means only that.

*Live half:* the same waste under an **order-blind** short-circuiting terminal.
`execution.py:432` sets `size = BATCH_SIZE` after the first *completed batch*,
not after a full round, so `.peek(fn).any_match(p)` that is not satisfied inside
the first 16 elements escalates straight to `WORKERS * BATCH_SIZE` ≈ 4096
elements in flight, every one running the whole chain. The old racing window's
total was 16. CLAUDE.md already concedes the concern "still applies at this
size"; this item is where that concession is actionable. `unordered()`, the
documented lever, does not help — the order-blind path is the one that
escalates fastest.

*Not analysed further here, deliberately.* The verdict is alive-or-dead only;
the sizing question (should the escalation hold a smaller step longer under a
short-circuiting consumer?) is open work, not a conclusion. One thing worth
knowing before starting: `fork-join-executor-and-spliterator` task 7.2 already
settled the **growth rule** — a Java-style +4-per-round increment measured 10x
more dispatches and ~2x worse wall time than the shipped one-step 4 -> 1024
jump — but never measured the first-round value `4` itself, which
`execution.py:196` still describes as "a starting point, not a measurement".
