## Why

`Stream.limit(n)` doesn't actually short-circuit: `_LimitOp.__call__` (`stream.py:52-60`) pulls an element from upstream *before* checking whether `max_size` has already been reached, so every `limit(n)` pipeline pulls `n+1` elements instead of `n`. For an expensive or effectful upstream (I/O calls, `peek()` side effects, generator work), that's one wasted unit of work per pipeline — and it means `.peek(seen.append).limit(2)` leaves `seen` with 3 elements instead of 2, which is surprising and diverges from Java's `Stream.limit()`, which genuinely stops pulling once `n` elements have been produced.

## What Changes

- `_LimitOp.__call__` (`stream.py`) is restructured to check `size_holder[0] >= max_size` *before* pulling the next element from `iterable`, instead of after. `limit(n)` now pulls exactly `n` elements from upstream (or fewer, if upstream is exhausted first) and closes upstream without having pulled an `n+1`th element.
- Under `.parallel()`, `size_holder` is already shared across all racing branches (`ParallelStream._parallel`'s `state_map`), so the fix keeps the existing global-limit guarantee (no more than `n` elements total across all branches) but changes *when* the shared source gets closed: instead of closing after one branch over-pulls, the branch that observes the shared count reaching `max_size` closes it before pulling further, and closure is made idempotent so a second racing branch closing (or pulling from) an already-closed shared source doesn't raise an unhandled exception out of `ParallelStream._parallel`'s task loop.
- No public API changes — `limit(n)`'s signature and return type are unchanged. Not a **BREAKING** change: the fix only reduces how many elements upstream sees per pipeline, which is only observable via side effects (`peek`, generator `StopIteration` timing), not via `limit()`'s own output.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `pipeline-composition`: the requirement covering `limit()`'s short-circuit behavior changes from "closes upstream after over-pulling by one element" to "closes upstream without pulling past the `n`th element," including the shared-source-closure behavior under `.parallel()`.

## Impact

- `src/snakestream/stream.py` — `_LimitOp.__call__`.
- `src/snakestream/parallel_stream.py` — no code change expected, but its shared-`state_map` contract with `_LimitOp` needs to keep holding once `_LimitOp` starts closing `iterable` earlier and more than once across racing branches.
- `tests/test_limit.py` — new regression coverage for exact-pull-count (no `n+1`th pull) and parallel shared-close idempotency; existing tests must keep passing unchanged.
