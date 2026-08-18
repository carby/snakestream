## 1. Stream.find_first()

- [x] 1.1 Replace the dead docstring stub (`stream.py:289-294`) with a real
      `find_first()` method: `async for n in self._compose(): return n`,
      returning `None` for an empty stream.

## 2. ParallelStream.find_first()

- [x] 2.1 Add a `find_first()` override in `parallel_stream.py`: when
      `self.is_ordered()` is `True`, pull via
      `self._sequential(self._chain[:], self._stream)` and return the first
      element (or `None` if empty).
- [x] 2.2 When `self.is_ordered()` is `False`, delegate to `find_any()`'s
      existing racing behavior.

## 3. Tests

- [x] 3.1 Add `tests/test_find_first.py`: non-empty and empty `Stream`,
      first-element-only pulled (rest of source untouched).
- [x] 3.2 Add ordered-`ParallelStream` coverage: a chain with per-element
      variable delay (mirroring `for_each_ordered()`'s existing test
      pattern) proving `find_first()` returns the true first element, not
      the first to arrive; empty-source case.
- [x] 3.3 Add unordered-`ParallelStream` coverage: `.unordered()` +
      `.find_first()` behaves like `find_any()` (no ordered-pull wait).

## 4. Docs

- [x] 4.1 Update README's parity table: uncomment/fill in the
      `find_first()` row (currently "Not implemented yet, depends on the
      implementation of `ordered()`").
- [x] 4.2 Update roadmap.md: move the `find_first()` **Now** item to
      **Done** with a summary, per the established pattern in this
      project's roadmap workflow.
