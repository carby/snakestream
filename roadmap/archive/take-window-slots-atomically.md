+++
id = "take-window-slots-atomically"
title = "Racing window slots are taken atomically (`take-window-slots-atomically`)"
filed = 2026-09-02
closed = 2026-09-02
outcome = "shipped"
shipped_as = "take-window-slots-atomically"
+++

**`take-window-slots-atomically`** (2026-09-02, shipped in `79e258f`) —
moved here 2026-09-02 from **Now**, where the change's own commit had left it
described as "scaffolded" although that same commit implemented and archived
it. `_Window` and `_guarded()` hand-rolled a counting semaphore out of a
counter and an `asyncio.Event`, and an `Event` cannot *hold* a slot: it only
broadcasts that one may exist. So a branch that waited for room had to ask
again after taking the lock, and that re-check was what forced the
doubly-nested `while True`, the `clear()`/`wait()` protocol and a barging
window with a regression test of its own. A synchronous `take()` — atomic
because it contains no `await`, so nothing runs between its check and its
increment — closed the window instead of compensating for it, and collapsed
the arm to one loop level.

*The gate was met, in advance.* It sits on the per-element path of the
windowed (barrier) arm, so the `collapse-terminal-collector-duplication`
`+10%` ns/element threshold applied; the measurement was banked in the
change's design.md rather than left for whoever started it. Three interleaved
runs, ordered delivery, min/median: `take()` at +1.2%/+0.3%, +0.4%/+0.9%,
−0.0%/−1.2% — straddling zero.

**`asyncio.Semaphore` itself is the measured rejection**, and it belongs in
this log rather than only in the change: it is exactly the missing primitive by
contract, and it cost **+5.7%/+7.3%, +3.9%/+6.0%, +6.4%/+5.6%** on the same
three runs, positive in all six statistics and absent from the order-blind path
it does not touch. `acquire()` is an `async def`, so it allocates a coroutine
frame per pull even on CPython's non-suspending fast path. Same family as
`add-callsite-dispatch`, `Sequential.value()`'s existence and the rejected
`merge()` generator — **abstraction against free, not abstraction against
cheaper abstraction** — and the first of them where the abstraction being
priced is a standard-library one. Do not re-propose the semaphore without new
evidence.

*What this is not.* It is not the roadmap's "Bound speculation separately
from read-ahead" (in **Later** when this was written; **Now** since
2026-09-05), which changes what the bound bounds. This changes no behaviour at
all: same value, same scaling, same fixedness for a run, `skip_specs: true`.
The two are independent and neither blocks the other.
