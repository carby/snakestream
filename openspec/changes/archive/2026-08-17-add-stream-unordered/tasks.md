## 1. Core Implementation

- [x] 1.1 Add `self._ordered: bool = True` instance state to
      `BaseStream.__init__` (`base_stream.py`)
- [x] 1.2 Add `BaseStream.unordered(self) -> BaseStream[T]`: sets
      `self._ordered = False` and returns `self`
- [x] 1.3 Add `BaseStream.is_ordered(self) -> bool`: returns `self._ordered`
- [x] 1.4 Propagate `self._ordered` onto the new instance constructed in
      `BaseStream.sequential()` and `BaseStream.parallel()`

## 2. Tests

- [x] 2.1 Test: a freshly constructed `Stream`/`ParallelStream` is ordered by
      default (`is_ordered()` returns `True`)
- [x] 2.2 Test: `unordered()` sets `is_ordered()` to `False`
- [x] 2.3 Test: `unordered()` returns `self` and can be chained with other
      intermediate ops
- [x] 2.4 Test: `unordered()` on one instance does not affect a separate
      `Stream` instance
- [x] 2.5 Test: ordering flag survives `.parallel()` after `.unordered()`
- [x] 2.6 Test: ordering flag survives `.sequential()` after `.unordered()`
- [x] 2.7 Test: ordering flag stays `True` across a mode switch when
      `unordered()` was never called

## 3. Docs

- [x] 3.1 Add `unordered()`/`is_ordered()` to README's `BaseStream` API
      section
- [x] 3.2 Move `roadmap.md`'s Now #1 (`BaseStream.iterator()`) from the Now
      table into Done (already implemented, table is stale) and move Now #2
      (`BaseStream.unordered()`) into Done once this change lands
