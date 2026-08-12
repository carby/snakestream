## 1. Implement the short-circuit fix

- [x] 1.1 Rewrite `_LimitOp.__call__` in `src/snakestream/stream.py` to check `size_holder[0] >= self._max_size` before pulling the next element (explicit `while`/`anext()` loop per `design.md`, replacing the `async for`), calling `iterable.aclose()` once the limit is reached and returning cleanly on `StopAsyncIteration` when upstream exhausts first.

## 2. Sequential regression tests

- [x] 2.1 Add a test asserting `.peek(fn).limit(n)` calls `fn` exactly `n` times (not `n + 1`) against a source with more than `n` elements.
- [x] 2.2 Add a test for `.limit(n)` against a source with exactly `n` elements, asserting all `n` elements are yielded and no error occurs.
- [x] 2.3 Add a test for `.limit(n)` against a source with fewer than `n` elements, asserting all available elements are yielded and no error occurs.
- [x] 2.4 Verify existing `tests/test_limit.py` cases (`test_limit_simple`, `test_limit_zero`, `test_limit_multiple`, `test_limit_state_not_shared_across_separate_streams`, `test_limit_state_fresh_on_second_composition`) still pass unchanged.

## 3. Parallel regression tests

- [x] 3.1 Add a test exercising `.parallel().limit(n)` against a source large enough to force multiple racing branches to observe the shared count reaching `n`, asserting the total output is exactly `n` elements and no exception escapes `collect()`.
- [x] 3.2 Verify existing `test_limit_parallel` still passes unchanged.

## 4. Validation

- [x] 4.1 Run `uv run pytest` and confirm the full suite passes.
- [x] 4.2 Run `uv run pytest --cov-fail-under=98` and confirm the coverage gate still passes.
- [x] 4.3 Run `uv run ruff check .` and `uv run ruff format --check .`.
- [x] 4.4 Run `uv run ty check src`.
