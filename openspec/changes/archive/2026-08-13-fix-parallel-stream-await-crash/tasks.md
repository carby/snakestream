## 1. Reproduce the crash

- [x] 1.1 Add a failing regression test to `tests/test_parallel.py` using a source whose `__anext__()` contains a real `await asyncio.sleep(0)`, driven through `.parallel()` (empty chain and a chain with at least one op), confirming it currently raises `RuntimeError: anext(): asynchronous generator is already running`.

## 2. Implement the guarded wrapper

- [x] 2.1 Add `_guarded(source, lock)` async generator helper to `parallel_stream.py` (or `base_stream.py` if shared use emerges): serializes `source.__anext__()` calls under an `asyncio.Lock`, yields outside the lock, and closes `source` via `source.aclose()` in a `finally` block.
- [x] 2.2 In `ParallelStream._parallel()`, create one `asyncio.Lock()` per call (alongside `state_map`) and pass `_guarded(iterable, lock)` — a fresh wrapper instance per branch — into each branch's `_sequential()` call instead of the raw shared `iterable`.

## 3. Verify existing guarantees still hold

- [x] 3.1 Run the existing `tests/test_parallel.py` suite and confirm no regression in ordering/racing behavior.
- [x] 3.2 Add/confirm a test that `.limit(n)` under `.parallel()` against a real-`await` source still closes the shared source idempotently when one branch reaches `max_size` while another branch is mid-pull (matching the `fix-stream-rerun-state` "second branch pulling from a closed shared source terminates cleanly" scenario).
- [x] 3.3 Add a test confirming downstream processing (e.g. an `await`-based `map()` mapper) can still run concurrently across branches even though upstream pulls are serialized — e.g. via call-order/timing assertions.

## 4. Regression pass and cleanup

- [x] 4.1 Run the failing test from 1.1 and confirm it now passes.
- [x] 4.2 Run full test suite (`uv run pytest`) and confirm the `--cov-fail-under=98` gate still passes.
- [x] 4.3 Run `uv run ruff check .`, `uv run ruff format --check .`, and `uv run ty check src`.
- [x] 4.4 Update `roadmap.md`: move item #1 from **Now** to **Done** with a summary of the fix, per the project's roadmap-maintenance convention.
