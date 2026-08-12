## Context

`_LimitOp.__call__` (`stream.py:52-60`) currently reads:

```python
async def __call__(self, iterable: AsyncGenerator, size_holder: list[int] | None = None) -> AsyncGenerator:
    if size_holder is None:
        size_holder = self.make_state()
    async for i in iterable:
        if size_holder[0] >= self._max_size:
            await iterable.aclose()
        else:
            size_holder[0] += 1
            yield i
```

`async for i in iterable` always pulls the next element *before* the loop body runs, so the check happens one element too late: on the call that would yield the `n`th element, the loop has already pulled and is holding the `(n+1)`th element by the time the next iteration's check fires `aclose()`. Net effect: `limit(n)` always pulls `n+1` elements from upstream (or exhausts upstream trying), even though it only ever yields `n`.

`ParallelStream._parallel()` shares one `size_holder` (via `state_map`) across `PROCESSES` racing branches that each run their own `_sequential()` composition of the same chain over the same underlying source. Because `size_holder` is shared, the total pulled across all branches is bounded, but any given branch calls `iterable.aclose()` on *its own* `iterable` argument — which, for the operation immediately following the shared source, is the shared source itself. Today this only happens after over-pulling, and only one branch "wins" the close race in practice because `asyncio.wait(..., FIRST_COMPLETED)` in `_parallel()` serializes when each branch's `__anext__()` resolves — but nothing currently makes a second `aclose()` (or a pull racing against a just-closed generator) safe by construction; it happens to work today because the existing tests don't stress two branches hitting the closed/closing generator simultaneously.

## Goals / Non-Goals

**Goals:**
- `limit(n)` pulls exactly `min(n, upstream length)` elements from upstream — never `n+1` — in both `Stream` and `ParallelStream`.
- Closing the shared source when the global count reaches `n` stays safe under racing branches: no unhandled exception escapes `ParallelStream._parallel()`'s task loop, and no branch is left awaiting a generator that was closed out from under it without a defined outcome.
- Preserve every existing requirement in `pipeline-composition`'s spec (fresh state per composition, no chain mutation, globally-correct parallel `limit()`).

**Non-Goals:**
- Not changing `limit()`'s public signature, return type, or its `distinct()`-adjacent state-reset contract.
- Not addressing `.parallel()`/`PROCESSES` naming (tracked separately in `roadmap.md`'s Next section).
- Not making `ParallelStream` order-preserving or otherwise changing its racing-branch execution model.

## Decisions

**Check-before-pull, not check-after-pull.** Replace the `async for` (which always pulls first) with an explicit `while True: pulled = await iterable.__anext__()` guarded by a size check performed *before* the pull:

```python
async def __call__(self, iterable: AsyncGenerator, size_holder: list[int] | None = None) -> AsyncGenerator:
    if size_holder is None:
        size_holder = self.make_state()
    while size_holder[0] < self._max_size:
        try:
            i = await anext(iterable)
        except StopAsyncIteration:
            return
        size_holder[0] += 1
        yield i
    await iterable.aclose()
```

Alternative considered: keep `async for` but track "have we already yielded `n`" and `break` instead of relying on the next loop iteration's pre-pull check. Rejected — `break` inside `async for` still leaves the just-pulled-but-undelivered next element stranded if the break happens after a pull; the loop body only ever runs *after* a pull succeeds, so there's no way to avoid the extra pull without abandoning `async for`'s implicit-pull structure. The explicit `while`/`anext()` form checks first by construction.

**Idempotent `aclose()` on the shared source.** `AsyncGenerator.aclose()` is already idempotent per Python's async generator protocol — calling it a second time on an already-closed generator is a no-op, not an error. The real risk is a second branch's `anext(iterable)` call racing against a concurrent `aclose()` on the same shared generator object. Since only one `asyncio` task runs at a time (single-threaded event loop) and `_parallel()` only has one branch's `__anext__()` task in flight touching a given shared upstream generator at a moment (each branch's task is `await`ed to completion — including running the `_LimitOp` closure body up to its next `yield`/`return` — before the next `asyncio.wait()` cycle picks the next ready task), `aclose()` and `anext()` on the shared generator never literally overlap mid-execution; they interleave at `await` boundaries like any other coroutine. A branch that calls `anext()` on an already-`aclose()`'d generator gets `StopAsyncIteration` (the standard closed-generator behavior), which the `while`/`except StopAsyncIteration: return` above already handles as a normal end-of-stream signal — no new exception-handling path is needed.

**No `finally`-based auto-close.** Considered wrapping the whole body in `try/finally: await iterable.aclose()` so upstream is always closed once the local branch's `limit` closure is torn down (e.g. via garbage collection or an unrelated downstream exception), matching Java-style resource cleanup. Rejected for this change — `BaseStream`'s existing `on_close()`/`close()` mechanism already owns explicit resource cleanup, and conflating it with `limit()`'s specific short-circuit-the-shared-source behavior would be a larger, separate design decision (how `limit()` interacts with `on_close()` isn't currently specified either way). Out of scope here; flagged as an Open Question below.

## Risks / Trade-offs

- [Risk] A downstream consumer relies on `peek()`/generator side effects seeing `n+1` elements (the current, buggy behavior) → Mitigation: this is exactly the bug being fixed per `roadmap.md`; the proposal documents it as an intentional (non-breaking, since `limit()`'s own output is unchanged) behavior change, and README's migration log is not updated since `limit(n)`'s return value and signature are unaffected.
- [Risk] `while`/`anext()` restructuring changes how `StopAsyncIteration` from a naturally-exhausted upstream is surfaced, compared to `async for`'s implicit handling → Mitigation: the `try/except StopAsyncIteration: return` branch reproduces `async for`'s termination behavior exactly (generator ends without yielding further), covered by the existing `test_limit_simple`/`test_limit_zero` tests plus a new exhausted-upstream-before-`n` test.
- [Risk] Parallel branches now check-then-close earlier, changing *which* branch "wins" the race to close the shared source run-to-run → Mitigation: this was already non-deterministic (depends on `asyncio.wait()` scheduling), and the spec only guarantees a *total* element count, not which branch performs the close; no test should depend on close ordering.

## Migration Plan

Not applicable — internal implementation change behind an existing method signature, single-commit fix with accompanying tests. No data migration, no phased rollout, no feature flag.

## Open Questions

- Should `limit()` eventually integrate with `BaseStream.on_close()` so a short-circuited upstream's registered close handlers fire as part of the short-circuit, rather than only via explicit `stream.close()`? Not resolved here; current behavior (calling `aclose()` on the generator itself, independent of `_close_handlers`) is preserved unchanged.
