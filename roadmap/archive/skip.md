+++
id = "skip"
title = "Added `Stream.skip(n)`"
filed = 2026-08-12
closed = 2026-08-12
outcome = "shipped"
+++

Added `Stream.skip(n)` — drops the first `n` elements pulled from upstream
and yields the rest, symmetric with the already-implemented `limit(n)`.
Implemented as `_SkipOp` (`stream.py`), mirroring `_LimitOp`'s
`make_state()`/shared-state pattern so `ParallelStream._parallel()`'s
existing generic `make_state()`-detection wires up correct parallel
behavior (exactly `n` total elements dropped across all racing branches,
not per-branch) with no `parallel_stream.py` changes needed. Unlike
`limit()`, `skip()` has no short-circuit available — the first `n`
elements must actually be pulled and discarded to advance upstream past
them. Added `tests/test_skip.py` plus parallel-specific regression tests
in `tests/test_parallel.py` (drops exactly `n` across branches, state
fresh across separate streams). No public API change to existing methods.
See `openspec/changes/add-stream-skip`.
