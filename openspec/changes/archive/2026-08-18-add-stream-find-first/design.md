## Context

`Stream.find_first()` (`stream.py:289-294`) is a dead docstring stub. The
comment blocking it ("until we have ordered parallel stream") predates
`BaseStream.unordered()`/`is_ordered()` (`stream-ordering` spec), which
exist specifically to unblock this item but are currently unconsumed
anywhere in the codebase.

Java's `Stream.findFirst()` always returns the first element in encounter
order, on both sequential and parallel streams — it does not race for
whichever result arrives first. On a parallel stream, the JDK achieves this
via ordered spliterator splitting: sub-ranges search concurrently, but a
match is only accepted once no earlier-ordered sub-range could still
produce one, so the result is deterministic. `findAny()` is the method
explicitly permitted to race and return non-deterministically; `findFirst()`
is only allowed to behave like `findAny()` when the stream is `.unordered()`
(encounter order is documented as relaxed in that case).

`ParallelStream._compose()` (`parallel_stream.py:28-62`) races `PROCESSES`
branches via `asyncio.wait(..., FIRST_COMPLETED)`, so a naive inherited
`find_first()` (`async for n in self._compose(): return n`) would return
whichever branch happens to finish its first pull fastest — not
first-encounter-order. `for_each_ordered()` (`stream.py:281-284`) already
solved an analogous problem by bypassing `_compose()` entirely and driving
`self._sequential(self._chain[:], self._stream)` directly, which is a
single-flight, strictly ordered pull through the chain regardless of
subclass.

## Goals / Non-Goals

**Goals:**
- `Stream.find_first()` returns the first element in encounter order
  (`T | None` for an empty stream).
- `ParallelStream.find_first()` returns the same encounter-order-correct
  result as `Stream.find_first()` when the stream is ordered (the default),
  matching Java's `findFirst()` parallel-stream guarantee.
- When `.unordered()` has been called, `ParallelStream.find_first()` is
  permitted to race like `find_any()`, matching Java's documented
  relaxation.

**Non-Goals:**
- No change to `find_any()`'s existing racing behavior.
- No attempt to replicate Java's actual ordered-spliterator-splitting
  mechanism — the ordered path uses a plain sequential pull (like
  `for_each_ordered()`), forfeiting `.parallel()`'s concurrency for this one
  terminal call, the same trade-off Java's own `forEachOrdered()`/ordered
  `findFirst()` make.
- No change to `unordered()`/`is_ordered()` semantics (`stream-ordering`
  spec) — this change only consumes the existing flag.

## Decisions

- **`Stream.find_first()` body**: identical to `find_any()`
  (`async for n in self._compose(): return n`), since `Stream._compose()`
  is already sequential. No `Stream`-level dependence on `is_ordered()` —
  Java's own `findFirst()` on a sequential stream doesn't consult
  orderedness either; the flag only matters once concurrent execution is in
  play.
- **`ParallelStream.find_first()` override**: branches on `self.is_ordered()`.
  - Ordered (default): `async for n in self._sequential(self._chain[:], self._stream): return n` — the same building block `for_each_ordered()` uses, guaranteeing first-encounter-order correctness at the cost of concurrency for this call.
  - Unordered: delegate to `find_any()`'s existing racing behavior
    (`self._compose()`-based), since there's no order guarantee to preserve
    and no reason to forfeit concurrency.
  - Alternative considered and rejected: implementing a true ordered-partial-search (mirroring Java's spliterator-splitting) to keep some concurrency in the ordered case. Rejected as disproportionate — no partition/spliterator concept exists in this codebase (tracked separately as `BaseStream.spliterator()` in roadmap **Later**, itself blocked on real multiprocess parallelism), and the `for_each_ordered()` precedent already established forfeiting concurrency as the accepted trade-off for order-correctness on a `ParallelStream` terminal op.
- **Where the override lives**: `parallel_stream.py`, as a new method on
  `ParallelStream`, not a conditional inside `stream.py`'s `find_first()` —
  matches the existing pattern of `ParallelStream` overriding `_compose()`/
  `is_parallel()` for subclass-specific behavior rather than `Stream`
  branching on `isinstance`.

## Risks / Trade-offs

- [Ordered `ParallelStream.find_first()` forfeits concurrency entirely, unlike Java's partial ordered-parallel search] → Accepted trade-off, consistent with `for_each_ordered()`'s existing precedent in this codebase; revisit only if/when `spliterator()`/real partitioned execution is built (roadmap **Later**).
- [A caller relying on `find_first()` for speed on a large `ParallelStream` gets no benefit over `Stream.find_first()`] → Documented via README parity notes; `find_any()` remains the fast/racing option, matching Java's own guidance to prefer `findAny()` over `findFirst()` when order doesn't matter.

## Migration Plan

Purely additive — no existing method changes behavior. Uncomment/implement
`find_first()` in `stream.py`, add the override in `parallel_stream.py`,
add tests, update README's parity table row (currently marked "Not
implemented yet").

## Open Questions

None.
