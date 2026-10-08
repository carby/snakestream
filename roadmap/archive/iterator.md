+++
id = "iterator"
title = "Added `BaseStream.iterator()`"
filed = 2026-08-13
closed = 2026-08-13
outcome = "shipped"
+++

Added `BaseStream.iterator()` — exposes the composed stream chain as a
plain `AsyncGenerator` without going through a collector, so a caller can
drive consumption directly via `async for`, `__anext__()`, or partial
iteration. Implemented as a thin wrapper around the existing `_compose()`
mechanism already used by terminal operations (`base_stream.py`), so it
works identically for `Stream` (sequential) and `ParallelStream` (parallel)
with no subclass-specific override, and — like other terminal ops —
composes non-destructively, leaving `self._chain` intact for later reuse.
Added `tests/test_iterator.py` covering: no elements pulled before
iteration starts, same elements/order as `collect(to_list)` for an
equivalent chain, partial consumption, `ParallelStream` behavior (racing
branches, unordered), and non-destructive composition (a second terminal
op after `iterator()` still sees the full chain). No public API removal;
purely additive. See `openspec/changes/archive/2026-08-13-add-stream-iterator`.
