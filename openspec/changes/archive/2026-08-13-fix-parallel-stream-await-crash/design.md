## Context

`ParallelStream._parallel()` (`parallel_stream.py`) builds `PROCESSES` independent async generators — each is its own call to `self._sequential(intermediaries[:], iterable, state_map)` — and races their `__anext__()` calls via `asyncio.wait(..., FIRST_COMPLETED)`, re-issuing a fresh `__anext__()` task for whichever branch just produced a result. All `PROCESSES` branches close over the *same* `iterable` object (`self._stream`, the single normalized source generator for the whole `ParallelStream`).

When a branch's intermediate-op chain is empty, `_sequential()` returns `iterable` itself, so two or more branches ARE the same async generator object — `asyncio.wait` then drives concurrent `__anext__()` calls into it. Even with a non-empty chain, every branch's innermost `async for` still ultimately awaits `iterable.__anext__()`; nothing serializes those awaits against each other. Python raises `RuntimeError: anext(): asynchronous generator is already running` the moment two overlap — silent under sync sources (each `__anext__()` call resolves synchronously within a single event-loop step, so `asyncio.wait` never actually observes two in flight at once), fatal under a source with a real `await` suspension point.

This is purely a `ParallelStream` concern. `Stream` (sequential) never has more than one consumer of `self._stream`, so `pipeline-composition`'s existing requirements (chain-not-consumed, per-composition state reset) are unaffected.

## Goals / Non-Goals

**Goals:**
- Make `.parallel()` safe over any `AsyncGenerator`-shaped source, including ones with genuine `await` suspension points.
- Preserve existing racing/fan-out behavior: branches still process downstream (`map`/`filter`/etc.) concurrently: only the raw pull from the shared upstream source is serialized.
- Preserve the already-fixed `limit()` shared-close idempotency (`fix-stream-rerun-state`): one branch closing the shared source after `size_holder[0] == max_size` must still be safe for another branch to subsequently pull from or close.

**Non-Goals:**
- Changing `.parallel()`'s ordering guarantees (`is_ordered()`/`unordered()` semantics untouched).
- Making `ParallelStream` true OS-thread/multiprocess parallelism — out of scope, tracked separately in `roadmap.md`'s Later bucket (`.parallel()`/`PROCESSES` rename).
- Batching or prefetching upstream pulls for throughput — this fix targets correctness, not performance.

## Decisions

### Serialize `__anext__()` on the shared source with an `asyncio.Lock`, via a per-branch wrapper generator

Introduce a small wrapper — an `async def` generator that takes the shared `iterable` and a single `asyncio.Lock` created once per `_parallel()` call — and give each of the `PROCESSES` branches its own instance of the wrapper (not the raw shared `iterable`) as the innermost source for its `_sequential()` chain:

```python
async def _guarded(source: AsyncGenerator, lock: asyncio.Lock) -> AsyncGenerator:
    try:
        while True:
            async with lock:
                try:
                    item = await source.__anext__()
                except StopAsyncIteration:
                    return
            yield item
    finally:
        await source.aclose()
```

Each branch gets a distinct wrapper *object*, so concurrent `__anext__()` calls from `asyncio.wait` land on distinct generators (legal) — but each wrapper's body only ever calls the shared `source.__anext__()` while holding the lock, so only one such call is ever in flight. The `yield item` happens outside the lock, so downstream processing for the item a branch just pulled proceeds concurrently with another branch's turn at the lock — fan-out behavior is preserved, only the raw pull is serialized.

**Alternatives considered:**
- *Single shared queue + one dedicated "pump" task reading `iterable` and fanning items out to per-branch queues.* Rejected: bigger structural change (an extra task, queue lifecycle, backpressure to design) for the same outcome; the lock-wrapper is a minimal, local fix to the exact race.
- *`anyio`/third-party "tee" primitive.* Rejected: no new dependency needed for a problem this scoped; `asyncio.Lock` is stdlib and already implicitly how the rest of the codebase reasons about coordination.
- *Detect a bare/empty chain and special-case routing all branches through one `_sequential()` call.* Rejected: doesn't fix the general case (non-empty chains still race `__anext__()` on the shared source inside their own `async for`), only the degenerate one.

### `_guarded`'s `finally: await source.aclose()` closes the *shared* source, not just the wrapper

Matching the existing idempotent-close contract for `limit()` (`_LimitOp.__call__` calling `iterable.aclose()`), `_guarded`'s teardown closes the underlying shared `source` whenever *any* wrapper instance is closed or exhausted — not just its own local generator frame. This is required for `limit()`'s existing "whichever branch reaches `max_size` first closes it for all branches" contract to keep working once branches see per-branch wrapper objects instead of the literal shared source. `source.aclose()` on an already-closed async generator is already a documented no-op, so no new idempotency handling is needed beyond what `aclose()` itself guarantees.

### Lock is created once per `_parallel()` call, not once per `ParallelStream` instance

The lock is local to a single `_parallel()` invocation (i.e., one composition), constructed alongside `state_map` at the top of the method and passed to each branch's `_guarded(iterable, lock)`. This mirrors the existing per-composition `state_map` lifecycle (`pipeline-composition`'s "state resets per composition" requirement) — a fresh lock per composition means no stale lock state (e.g. held-forever from a cancelled prior composition) can leak into a later one.

## Risks / Trade-offs

- **[Serialization removes some of the parallelism `.parallel()` implies for the upstream pull itself]** → Acceptable: the source was never actually safe to pull concurrently (that's the bug), so this trades an unsound "parallel pull" for a correct serialized one. Downstream per-item processing (the actual `map`/`filter`/etc. work `.parallel()` is meant to overlap) remains concurrent.
- **[Lock contention under a source with very cheap `await` points could reduce throughput vs. today's (broken) fully-concurrent pulls]** → Out of scope per Non-Goals; correctness takes priority, and today's "throughput" on a real-async source is a crash, not a baseline to protect.
- **[`_guarded`'s `finally` closing the shared `source` on any single wrapper's teardown could close it earlier than intended if only one branch is being torn down independently (e.g. via GC) while others are still active]** → Mitigated by scoping this risk to the same case already handled today: `_parallel()`'s own `finally` block already cancels and closes all remaining branch tasks together on early exit, so all wrapper teardowns already happen as a group in the existing early-exit path. Regression tests should cover a branch closing early via `limit()` mid-race, matching the existing `fix-stream-rerun-state` coverage.

## Open Questions

None — the fix is scoped to `ParallelStream._parallel()`/`_guarded`, with no public API or cross-cutting impact.
