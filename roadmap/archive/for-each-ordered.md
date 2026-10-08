+++
id = "for-each-ordered"
title = "Added `Stream.for_each_ordered()`"
filed = 2026-08-17
closed = 2026-08-17
outcome = "shipped"
+++

Added `Stream.for_each_ordered(consumer)` (`stream.py`) — an ordered variant
of `for_each()`, invoking `consumer` in the stream's encounter order even
when called on a `ParallelStream` instance, matching Java's
`Stream.forEachOrdered()`. `for_each()` drives consumption via
`self._compose()`, which `ParallelStream` overrides to fan the chain out
across racing branches with no order guarantee; `for_each_ordered()`
instead drives consumption via `self._sequential(self._chain[:],
self._stream)` directly — the same building block `Stream._compose()`
already uses — so it gets a strictly ordered, single-flight pull through
the chain regardless of which subclass `self` is. This intentionally
forfeits `.parallel()`'s concurrency for that one terminal call, the same
trade-off Java's own `forEachOrdered()` makes on a parallel stream. The
existing `BaseStream._ordered`/`unordered()` flag (see below) is not
consumed here — every snakestream source has a real underlying order, and
Java's own `forEachOrdered()` Javadoc ties the "if the stream has one"
caveat to streams with no defined encounter order to begin with, which
`unordered()` doesn't currently model. `for_each()`'s existing behavior is
unchanged. Added `tests/test_for_each_ordered.py`: ordered/async-consumer
coverage on sequential `Stream`, plus a same-chain-and-timing pair of
parallel tests using a jumbled source and a positional (not value-based)
per-element delay in a `.map()` step — one showing plain `for_each()` on a
`ParallelStream` can come out scrambled under that reordering pressure, the
other showing `for_each_ordered()` on the identical chain stays in source
order. See `openspec/changes/add-stream-foreach-ordered`.
