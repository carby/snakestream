## Why

`BaseStream._compose()` and the closures queued by stateful intermediate ops (`distinct()`, `limit()`) both leak execution state across runs: `_sequential()` (`base_stream.py:38,40`) calls `pop(0)` on the caller's own `self._chain` list, so composing the pipeline once empties it, and `distinct()`/`limit()` (`stream.py:155-194`) initialize their `seen`/`size` state outside the closure they queue, so that state persists across separate compositions of the same closure. Together these mean a second terminal operation on the same `Stream` — or reusing a `distinct()`/`limit()` chain against a fresh source — silently returns wrong (usually empty) results instead of erroring or repeating the first run's output. `ParallelStream._parallel` already avoids the first bug by copying the list (`intermediaries[:]`), so the two subclasses currently honor different contracts for the same `_compose()` call.

## What Changes

- Fix `BaseStream._sequential()` to stop mutating `self._chain` in place (copy the list, or iterate without popping), so composing a stream's chain is a non-destructive, repeatable operation — matching the contract `ParallelStream._parallel` already follows.
- Move the `seen`/`size` state that `distinct()` and `limit()` currently initialize outside their `async def fn` closures (`stream.py:155-194`) to be initialized inside `fn`, so each composition of the chain gets fresh state rather than sharing state across runs.
- Decide and document `ParallelStream`'s behavior for `distinct()`/`limit()` explicitly: today all racing branches share one `seen`/`size` because the closure state is external; moving state inside `fn` changes this unless `ParallelStream` is special-cased to keep sharing it. The change must state which behavior is intended and implement it consistently, not leave it as an accident of variable scope.
- Add regression tests asserting that calling a terminal operation (e.g. `collect()`) twice on the same `Stream` yields the same result both times, including chains containing `distinct()`/`limit()`, for both `Stream` and `ParallelStream`.

## Capabilities

### New Capabilities
- `pipeline-composition`: Defines the contract for `BaseStream._compose()`/`_sequential()`/`_parallel()` — specifically, that composing a stream's queued closures into an executable pipeline must not mutate or consume the stream's own chain state, so a stream (and any closure state it queued) can be composed and run more than once with consistent results.

### Modified Capabilities
(none — no existing spec covers pipeline composition or the `distinct()`/`limit()` closures; this is new spec territory, not a change to `stream-construction` or the other existing specs)

## Impact

- `src/snakestream/base_stream.py` — `_sequential()` (chain mutation fix).
- `src/snakestream/stream.py` — `distinct()`, `limit()` closure state relocation.
- `src/snakestream/parallel_stream.py` — `_parallel()`, to keep or intentionally change shared-state semantics for `distinct()`/`limit()` under parallel execution.
- Test suite: new regression tests for repeated terminal-op calls on one `Stream`/`ParallelStream` instance.
- No public API signature changes; behavior-only fix, not marked **BREAKING** since the current behavior (silently wrong results on reuse) is a bug, not documented behavior.
