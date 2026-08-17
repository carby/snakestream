## Context

`for_each(consumer)` (`stream.py`) drives consumption via `self._compose()`, which `ParallelStream` overrides to fan the chain out across `PROCESSES` racing branches (`_parallel()`), so element order at the consumer is nondeterministic under `.parallel()`. `BaseStream` already tracks an `_ordered` flag (`unordered()`/`is_ordered()`), defaulting to `True`, added specifically to unblock this item but not yet consumed by anything.

`ParallelStream._parallel()`'s racing-branch model has no mechanism today to reconcile out-of-order branch completions back into encounter order without buffering — that reconciliation is out of scope for this change (tracked separately in the roadmap's **Next**-bucket Sink-chain redesign).

## Goals / Non-Goals

**Goals:**
- `for_each_ordered()` invokes the consumer in encounter order for both `Stream` and `ParallelStream`, matching Java's `forEachOrdered()` contract.
- No change to `for_each()`'s existing behavior or performance characteristics.

**Non-Goals:**
- Making `.parallel()` execution itself preserve order (i.e., no change to `_parallel()`/racing-branch mechanics).
- Consuming `is_ordered()`/`unordered()` to skip the ordering guarantee when a stream has been marked unordered — Java's `forEachOrdered()` ignores encounter-order-optionality opt-outs for this method specifically (per `Stream.forEachOrdered` Javadoc, it performs the action in encounter order *if the stream has one*; `unordered()` streams have no defined encounter order to begin with). Given `BaseStream._ordered` currently has no other consumer and every snakestream source has a real underlying order (list/generator/iterator), treating `_ordered` as advisory-only here (i.e., not gating behavior on it) keeps this change small; revisit if a future item gives `unordered()` teeth elsewhere.

## Decisions

**Drive `for_each_ordered()` through `BaseStream._sequential()` directly, not `self._compose()`.**

`self._compose()` resolves to `ParallelStream._compose()` (parallel/unordered) when called on a `ParallelStream` instance. `for_each_ordered()` instead calls `self._sequential(self._chain[:], self._stream)` explicitly — the same building block `Stream._compose()` already uses — so it gets a strictly ordered pull through the chain regardless of which subclass `self` is. This mirrors Java: `forEachOrdered()` on a parallel stream still incurs the cost of sequential-equivalent ordering.

Alternative considered: add an `_ordered_compose()` hook that `Stream` and `ParallelStream` each implement (`Stream` delegating to `_compose()`, `ParallelStream` delegating to `_sequential()`). Rejected as unnecessary indirection — `BaseStream._sequential()` is already accessible on `self` in both subclasses, so no new virtual dispatch is needed for a single call site.

**Implement as a new `for_each_ordered()` method, not a parameter on `for_each()`.**

Matches Java's API shape (two distinct methods) and the project's stated preference for Java-parity naming over invented flags/params.

## Risks / Trade-offs

- [Calling `for_each_ordered()` on a `ParallelStream` silently forfeits the parallelism the caller may expect] → Matches Java's own documented trade-off for `forEachOrdered()` on parallel streams; no additional mitigation needed beyond documenting it in the method's contract (spec + eventual docstring).
