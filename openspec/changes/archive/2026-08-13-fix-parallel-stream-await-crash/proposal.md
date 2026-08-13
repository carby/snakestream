## Why

`ParallelStream._parallel()` (`parallel_stream.py`) fans `PROCESSES` racing branches out over the *same* underlying `self._stream` async generator, each branch calling `__anext__()` on it independently via `asyncio.wait(..., FIRST_COMPLETED)`. A single async generator instance doesn't support overlapping `anext()` calls; as soon as the source has a genuine suspension point (a real `await`), Python raises `RuntimeError: anext(): asynchronous generator is already running`. This breaks `.parallel()` for any authentically async source — network, file, or DB-backed generators — which is exactly the use case `.parallel()` exists for. Existing parallel tests all use sync sources where `_normalize()` never truly cedes control, so the collision has gone unnoticed until now.

## What Changes

- Serialize access to the shared upstream source in `ParallelStream._parallel()` so that only one racing branch is ever awaiting `__anext__()` on it at a time, while still allowing the branches' own downstream processing (`map`/`filter`/etc. closures) to run concurrently.
- No public API change: `.parallel()` continues to accept any `AsyncGenerator`-shaped source and race `PROCESSES` branches over the composed chain.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `pipeline-composition`: adds a requirement that `ParallelStream._parallel()`'s racing branches serialize their `__anext__()` calls against the shared upstream source, so a source with real `await` suspension points no longer raises `RuntimeError: anext(): asynchronous generator is already running`.

## Impact

- `src/snakestream/parallel_stream.py` — `_parallel()`'s branch-fan-out mechanism.
- Possibly `src/snakestream/base_stream.py` — if the serialization helper is shared/general enough to live alongside `_sequential()`/`_compose()`.
- Tests: new regression coverage in `tests/test_parallel.py` using a source with a real `await asyncio.sleep(0)` suspension point.
