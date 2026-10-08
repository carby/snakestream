+++
id = "implement-find-first"
title = "Implemented `Stream.find_first()`"
filed = 2026-08-18
closed = 2026-08-18
outcome = "shipped"
+++

Implemented `Stream.find_first()` (`stream.py`), matching Java's
`Stream.findFirst()`. The previous body was a dead
docstring-commented-out stub — a string literal, never executed — with a
comment claiming it was blocked on "ordered parallel stream." That
blocker didn't actually apply to `Stream`: `Stream._compose()` is already
sequential, so `find_first()` there is identical in body to `find_any()`.
The real gap was narrower and `ParallelStream`-specific:
`ParallelStream._compose()` races `PROCESSES` branches via
`asyncio.wait(..., FIRST_COMPLETED)`, so first-*arrival* isn't
first-*encounter-order*. Fixed by adding a `ParallelStream.find_first()`
override that checks `self.is_ordered()`: when ordered (the default),
pulls via `self._sequential(self._chain[:], self._stream)` — the same
building block `for_each_ordered()` uses — for a strictly ordered,
single-flight pull through the chain, guaranteeing the true first element
in encounter order at the cost of `.parallel()`'s concurrency for this
one terminal call (the same trade-off Java's own `forEachOrdered()`/
ordered `findFirst()` make); when the stream has been marked
`unordered()`, delegates to `find_any()`'s existing racing behavior,
matching Java's documented relaxation of `findFirst()`'s encounter-order
guarantee for unordered streams. This is the first consumer of the
`is_ordered()`/`unordered()` flag added by `add-stream-unordered`. Added
`tests/test_find_first.py`: non-empty/empty `Stream`,
first-element-only pulled, and — mirroring `test_for_each_ordered.py`'s
jumbled-source-with-positional-delay pattern — ordered-`ParallelStream`
coverage proving `find_first()` returns the true first element rather
than the first to arrive, plus unordered-`ParallelStream` coverage
showing it races without waiting for a full ordered pull. Updated
README's parity table (`find_first()` row, previously "Not implemented
yet"). No breaking changes. See
`openspec/changes/add-stream-find-first`.
