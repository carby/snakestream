## 1. Implementation

- [x] 1.1 Add `iterator(self) -> AsyncGenerator[T, None]` to `BaseStream` (`src/snakestream/base_stream.py`), returning `self._compose()` directly, alongside `sequential()`/`parallel()`.

## 2. Tests

- [x] 2.1 Add `tests/test_iterator.py`: `.iterator()` on a `Stream` returns an `AsyncGenerator` without pulling any elements before iteration starts.
- [x] 2.2 `async for` over `.iterator()`'s result yields the same elements, same order, as `collect(to_list)` on an equivalent chain.
- [x] 2.3 Partial consumption (a few `__anext__()` calls, then stop) works without error.
- [x] 2.4 `.iterator()` on a `ParallelStream` yields the expected elements (unordered) consistent with existing parallel test patterns in `tests/test_parallel.py`.
- [x] 2.5 Chain is not consumed/mutated by `.iterator()`: a terminal op called after a fully-consumed `.iterator()` on the same instance still sees the full chain (mirrors existing `pipeline-composition` regression tests).

## 3. Docs

- [x] 3.1 Move `iterator()` out of README's "Left to do" `BaseStream` list into the `BaseStream` API table (`README.md`), following the existing row format.
