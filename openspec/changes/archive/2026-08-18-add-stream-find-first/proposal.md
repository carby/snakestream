## Why

`Stream.find_first()` (`stream.py:289-294`) is a dead docstring-commented-out
stub — a string literal, never executed — with a comment claiming it's
blocked on "ordered parallel stream." That blocker no longer applies:
`BaseStream.unordered()`/`is_ordered()` (`stream-ordering` spec) already
exist and are otherwise unconsumed, built specifically to unblock this item,
and `for_each_ordered()`'s ordered-pull pattern is a direct precedent for
getting correct first-encounter-order semantics out of a `ParallelStream`.

## What Changes

- Implement `Stream.find_first()` returning the first element in encounter
  order (`T | None` for an empty stream), matching Java's
  `Stream.findFirst()`. On `Stream`, `_compose()` is already sequential, so
  the body is identical to `find_any()`.
- Add a `ParallelStream.find_first()` override: when `is_ordered()` is
  `True` (the default), pull via a strictly ordered single-flight
  `self._sequential(self._chain[:], self._stream)` (the same building block
  `for_each_ordered()` uses) to guarantee first-encounter-order correctness,
  matching Java's `findFirst()` on a parallel stream (deterministic,
  encounter-order result even though internally Java achieves it via
  ordered spliterator splitting rather than a plain sequential pull); when
  the stream has been marked `unordered()`, race like `find_any()` since
  Java explicitly relaxes the encounter-order guarantee in that case.
- Update README: uncomment/fill in the `find_first()` parity-table row and
  migration log if relevant.

## Capabilities

### New Capabilities
- `stream-find-first`: defines `find_first()`'s contract on `Stream` and
  `ParallelStream`, including its dependence on the `is_ordered()` flag for
  choosing an ordered vs. racing pull strategy.

### Modified Capabilities
(none — `stream-ordering`'s existing requirements are consumed as-is, not
changed)

## Impact

- `src/snakestream/stream.py`: replace the dead docstring stub with a real
  `find_first()` method.
- `src/snakestream/parallel_stream.py`: add a `find_first()` override.
- `README.md`: parity table update.
- New `tests/test_find_first.py`.
