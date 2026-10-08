+++
id = "iterative-sequential"
title = "Rewrote `BaseStream._sequential()` from recursion to a loop"
filed = 2026-08-17
closed = 2026-08-17
outcome = "shipped"
+++

Rewrote `BaseStream._sequential()` (`base_stream.py`) from recursion +
`list.pop(0)` to an iterative loop over the queued closures. The old
implementation recursed once per chained intermediate operation and
popped from the front of the list on each call, giving O(n) Python stack
depth (risking `RecursionError` on a long `.map()/.filter()/...` chain)
and O(n²) time (since `list.pop(0)` is itself O(n), called n times) for a
chain of n ops. Fixed by iterating the closures in order with a plain
`for` loop and threading `iterable` through each step, dropping the
`pop(0)` entirely — `_compose()` (`_sequential()`'s only caller) needed
no changes since it already passes a fresh list copy. No change to
`_sequential()`'s signature, return value, or `state_map` per-closure
state lookup. Added `test_sequential_long_chain_does_not_recurse_at_build_time`
(`tests/test_sequential.py`), calling `_sequential()` directly with a
chain of `sys.getrecursionlimit() * 2` identity closures to isolate the
build-time traversal this fix addresses.

**Scope note, discovered during implementation:** this only fixes
*building* the pipeline. Each individual op in `stream.py` (`filter`,
`map`, `flat_map`, `sorted`, `peek`, `_DistinctOp`, `_LimitOp`,
`_SkipOp`) is itself implemented as `async def fn(iterable): async for i
in iterable: yield ...`, so *consuming* a long chain still recurses once
per chained op at the `async for`/`__anext__()` delegation level,
confirmed unchanged before and after this fix by testing a long
`.map()` chain end-to-end. Fully closing the original roadmap item's
stated risk requires a push-based execution-model redesign across every
op in `stream.py` and `parallel_stream.py` — out of scope here and
tracked as a new **Next**-bucket item. See
`openspec/changes/rewrite-sequential-iterative`.
