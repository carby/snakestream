+++
id = "parallel-stream-await-crash"
title = "Fixed `ParallelStream` crashing on a source with a real `await`"
filed = 2026-08-13
closed = 2026-08-13
outcome = "shipped"
+++

Fixed `ParallelStream` crashing on any source with a real `await`
suspension point. `ParallelStream._parallel` (`parallel_stream.py`) fanned
`PROCESSES` racing branches out over the *same* shared `self._stream`
async generator, each calling `__anext__()` on it independently; a source
with a genuine `await` inside `__anext__()` raised
`RuntimeError: anext(): asynchronous generator is already running` as soon
as two branches' pulls overlapped. Fixed by adding a `_guarded(source,
lock)` wrapper generator (`parallel_stream.py`): each branch gets its own
wrapper instance, but all wrappers serialize their calls into the shared
source's `__anext__()` (and `aclose()`) through one `asyncio.Lock` created
per `_parallel()` call, so only one pull is ever in flight while
downstream per-branch processing (`map`/`filter`/etc.) still runs
concurrently. Fixing this surfaced a second, previously-latent race in
`_LimitOp` (`stream.py`): its check-then-pull-then-increment sequence
against the shared `size_holder` wasn't atomic once the pull could
genuinely cede control, letting multiple branches pass the size check
before any incremented and yield more than `n` elements in total. Fixed
by reordering to reserve the slot (increment) *before* pulling, so the
check-and-reserve step has no `await` between them and stays atomic
across racing branches. Added `tests/test_parallel.py` coverage using a
source with a real `await asyncio.sleep(0)` suspension point: empty and
non-empty chains no longer raise, `.limit(n)` stays at-or-under `n` and
closes the shared source safely across branches, and downstream mapper
invocations still overlap despite serialized upstream pulls (timing
assertion). No public API change. See
`openspec/changes/fix-parallel-stream-await-crash`.
