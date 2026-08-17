## 1. Type aliases

- [x] 1.1 Add `Supplier` alias (`Callable[[], R | Awaitable[R]]`) to `type.py`
- [x] 1.2 Add `BiConsumer` alias (`Callable[[R, T], None | Awaitable[None]]`) to `type.py`

## 2. Implementation

- [x] 2.1 Add `@overload` signatures to `Stream.collect()` (`stream.py`) for both the existing `collect(collector)` form and the new `collect(supplier, accumulator, combiner)` form
- [x] 2.2 Implement the runtime body: branch on arg count/shape, call `supplier()` via `_maybe_await`, then `async for` over `self._compose()` calling `accumulator(container, element)` via `_maybe_await` per element, then return the container
- [x] 2.3 Confirm `combiner` is accepted in the signature but never referenced in the runtime body (matches design.md's Non-Goals)
- [x] 2.4 Add/verify docstring or inline note on `collect()` stating `combiner` is accepted for Java signature parity only and is not invoked

## 3. Tests

- [x] 3.1 Add `tests/test_collect.py` (or extend existing collect tests) covering: sync supplier+accumulator, async supplier+accumulator, empty stream, existing single-arg `collect(collector)` unchanged
- [x] 3.2 Add a test asserting `combiner` is never called, sequential `Stream`
- [x] 3.3 Add a test asserting `combiner` is never called and all elements land in the container, `ParallelStream`

## 4. Verification

- [x] 4.1 `uv run pytest` passes
- [x] 4.2 `uv run ruff check .` and `uv run ruff format --check .` pass
- [x] 4.3 `uv run ty check src` passes
- [x] 4.4 `uv run pytest --cov-fail-under=98` passes
- [x] 4.5 Update README.md's Java Stream API parity table to mark `collect(supplier, accumulator, combiner)` as implemented
- [x] 4.6 Add a roadmap.md item (Later bucket, alongside the `.parallel()`/`PROCESSES` rename decision) to wire up `combiner` — i.e. actually invoke it to merge independently-accumulated partitions — once that blocking decision is made, mirroring roadmap item #4's same blocker for `reduce(identity, accumulator, combiner)`
