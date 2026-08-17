## Context

`BaseStream._sequential()` (`base_stream.py:36-49`) is the sole engine behind sequential composition — it's called by `_compose()` for every `Stream` terminal operation, and by each `ParallelStream` branch's own `_sequential()` call in `_parallel()`. It currently recurses once per queued intermediate-operation closure, popping the closure to apply off the *front* of the list (`intermediaries.pop(0)`) each call:

```python
def _sequential(self, intermediaries, iterable, state_map=None):
    if len(intermediaries) == 0:
        return iterable
    fn = intermediaries.pop(0)
    state = state_map.get(fn) if state_map is not None else None
    next_iterable = fn(iterable, state) if state is not None else fn(iterable)
    if len(intermediaries) == 0:
        return next_iterable
    return self._sequential(intermediaries, next_iterable, state_map)
```

Two problems: recursion depth grows with chain length (risking `RecursionError` on a long `.map()/.filter()/...` chain), and `list.pop(0)` is O(n) per call, making the whole traversal O(n²) for n ops.

## Goals / Non-Goals

**Goals:**
- Eliminate the per-op recursion so chain length no longer risks `RecursionError`.
- Eliminate the O(n²) traversal cost from front-popping.
- Preserve `_sequential()`'s exact external contract: same signature, same return value, same `state_map` per-closure state lookup, called the same way by `_compose()` and (indirectly, via each branch's own composition) `ParallelStream._parallel()`.

**Non-Goals:**
- No change to `_compose()`, `sequential()`, `parallel()`, or any terminal/intermediate operation's behavior.
- No change to the closure signature contract (`fn(iterable)` or `fn(iterable, state)`).
- Not addressing `ParallelStream._parallel()`'s own separate composition logic — it calls `_sequential()` per branch already receiving a fresh list copy, and is unaffected by this rewrite.

## Decisions

**Iterative loop over an index (or `deque.popleft()`), not `pop(0)` on a list.**
The existing signature receives `intermediaries` as a caller-owned copy (`_compose()` already passes `self._chain[:]`), so it's safe to mutate freely without affecting `self._chain`. Two equivalent options:
- Iterate by index (`for fn in intermediaries: ...`), no mutation needed at all — simplest, and avoids the O(n) pop cost entirely since indexing/iterating a list is O(1) amortized per step.
- Convert to `collections.deque` and `popleft()` if mutating-as-you-go is preferred for symmetry with the old code.

Plain index-based iteration is preferred: it's simpler, needs no import, and matches how the rest of the codebase iterates lists.

**Keep the `state_map` lookup identical.** Each closure's state is still resolved via `state_map.get(fn)` per step; only the traversal mechanism (recursion → loop) and the pop strategy (front-pop → indexed iteration) change.

## Risks / Trade-offs

- [Behavioral drift for closures with side effects on `intermediaries` itself] → None expected: closures only ever receive `iterable`/`state`, never the list itself, so traversal-order change (which is none — order is preserved) is the only thing that could matter, and iteration order is unchanged (still first-to-last).
- [Existing tests relying on `_sequential()`'s exact recursive call pattern] → None known; `pipeline-composition` tests exercise `_compose()`'s observable behavior (non-destructive chain, per-composition state reset), not its internal recursion, so they should pass unmodified and serve as the regression suite.
- [This fix does not fully close the roadmap item's stated risk] → **Discovered during implementation**: each individual op in `stream.py` (`filter`, `map`, `flat_map`, `sorted`, `peek`, `_DistinctOp`, `_LimitOp`, `_SkipOp`) is itself implemented as `async def fn(iterable): async for i in iterable: yield ...`, so *consuming* a long chain still recurses once per chained op at the `async for`/`__anext__()` delegation level, independent of how `_sequential()` builds the chain. Confirmed by testing: a chain of `sys.getrecursionlimit() * 2` `.map()` calls still raises `RecursionError` on *consumption* both before and after this change. Fully closing the gap requires redesigning every op from generator-delegation (`AsyncGenerator -> AsyncGenerator`) to a push-based model (a single driving loop threading each item through all ops via a plain `for op in ops:` loop, similar to Java Stream's `Sink` chain) — a much larger change than this one, deliberately left out of scope here and tracked as a separate follow-up change (mitigation: scope it explicitly rather than silently expand this change's blast radius).

## Migration Plan

Single internal-only change, no data migration or rollout sequencing needed. Land as one commit: rewrite `_sequential()`, run full test suite plus the new long-chain regression test, and confirm `ty`/coverage gates still pass.
