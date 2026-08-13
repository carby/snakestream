## Context

`BaseStream._compose()` already builds the full lazy pipeline (`self._sequential()` for `Stream`, `self._parallel()` for `ParallelStream`) and is reused unchanged by every existing terminal operation (`collect()`, `for_each()`, `reduce()`, etc.) as well as by `sequential()`/`parallel()`. `iterator()` needs no new composition machinery — it's a thin, non-consuming wrapper around a call that already exists.

## Goals / Non-Goals

**Goals:**
- Let callers get the raw composed `AsyncGenerator[T, None]` and drive iteration themselves, without a collector.
- Behave identically on `Stream` and `ParallelStream` with zero subclass-specific code.

**Non-Goals:**
- No sync-iterator equivalent. Every source is normalized to `AsyncGenerator` internally (per `CLAUDE.md`); bridging to a blocking/sync iterator would need its own event-loop-pumping machinery, which is out of scope and has no motivating use case yet.
- No change to `_compose()`, `_sequential()`, or `_parallel()` themselves.

## Decisions

- **Return `self._compose()` directly, no wrapper object.** `AsyncGenerator` already satisfies `async for`, manual `__anext__()`, and `.aclose()`, so returning it as-is is both the minimal implementation and the most Pythonic — there's no `java.util.Iterator`-shaped interface to imitate since Python's iterator protocol is duck-typed. Considered wrapping in a dedicated `AsyncIterator` class for API symmetry with Java, rejected as unnecessary indirection with no behavioral benefit.
- **Place `iterator()` on `BaseStream`, not `Stream`.** Matches the roadmap item and README's existing "Left to do" listing of `iterator()` under `BaseStream`, and mirrors `sequential()`/`parallel()`, which already live there for the same reason (subclass-agnostic, just calls `_compose()`).
- **No `__aiter__` on `BaseStream` in this change.** Making `BaseStream` itself directly `async for`-able is a natural follow-on (`async for x in stream:` instead of `async for x in stream.iterator():`) but is a separate, slightly bigger API-surface decision (does composing on iteration match user expectation of when composition happens?) not covered by the roadmap item. Left as a possible future addition, not blocking this one.

## Risks / Trade-offs

- [Caller composes more than once by calling `iterator()` twice] → Each call is an independent, correct composition per the existing non-destructive `_compose()` contract (`pipeline-composition` spec) — not a new risk, just relying on an existing guarantee.
- [Caller never fully consumes the returned generator] → Same as any other partially-consumed async generator in this codebase already (e.g. `find_any()`'s early return); no new resource-lifecycle concern introduced.
