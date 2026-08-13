## Why

`BaseStream` has no way to pull the composed pipeline as a plain iterator — the only ways to consume a stream today are the terminal operations (`collect()`, `for_each()`, `reduce()`, etc.), which each drive the whole pipeline to completion internally. Java's `Stream.iterator()` exists precisely for callers who want to drive consumption themselves (e.g. manual `while`/`for` loops, early abandonment, interleaving with other async work) without reaching for a collector. This is the top item in `roadmap.md`'s **Now** bucket: no blockers, no dependents, an independent addition.

## What Changes

- Add `BaseStream.iterator()`, a terminal-shaped operation that composes the queued chain (via the existing `_compose()`) and returns the resulting `AsyncGenerator[T, None]` directly to the caller, instead of driving it to completion. The caller then owns iteration (`async for`, manual `__anext__()`, partial consumption, etc.).
- Works identically on `Stream` and `ParallelStream`, since both already implement `_compose()` (`_sequential()` vs. `_parallel()`) — `iterator()` needs no per-subclass override.
- No sync-iterator variant: since every stream is normalized into an `AsyncGenerator` internally (per `CLAUDE.md`), there's no sync form to expose without a blocking bridge, which is out of scope. This matches the project's existing all-async posture (contrast with Java's `iterator()`, which is sync because the underlying `Stream` is sync).

## Capabilities

### New Capabilities
- `stream-iterator`: `BaseStream.iterator()` — composes the current chain and hands the caller the raw `AsyncGenerator`, without consuming it or requiring a collector.

### Modified Capabilities
(none — `pipeline-composition`'s existing `_compose()` contract is reused unchanged, not modified)

## Impact

- `src/snakestream/base_stream.py`: new `iterator()` method on `BaseStream`.
- `README.md`: move `iterator()` from "Left to do" to the `BaseStream` table, per `CLAUDE.md`'s parity-tracking instructions.
- New tests (`tests/test_iterator.py`) covering `Stream` and `ParallelStream`.
- No breaking changes; purely additive.
