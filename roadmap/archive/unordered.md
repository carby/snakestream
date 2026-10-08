+++
id = "unordered"
title = "Added `BaseStream.unordered()`"
filed = 2026-08-13
closed = 2026-08-13
outcome = "shipped"
+++

Added `BaseStream.unordered()` — marks a stream instance as not
order-dependent, mirroring Java's `BaseStream.unordered()`. Implemented as
a `self._ordered: bool` flag on `BaseStream` (`base_stream.py`), defaulting
to `True`; `unordered()` sets it `False` and returns `self`, matching the
mutate-and-return-self convention every other chainable method already
follows; `is_ordered()` exposes the current value, mirroring the existing
`is_parallel()` query method. `sequential()`/`parallel()` now copy the
flag onto the new instance they construct rather than resetting it, so an
`unordered()` declaration survives a mode switch. Purely additive
bookkeeping — no change to actual iteration order in `Stream` or
`ParallelStream`; it exists to unblock the planned `forEachOrdered()` and
`find_first()`/`find_any()` distinction (`stream.py`'s disabled
`find_first` stub), neither of which consume the flag yet. Added
`tests/test_unordered.py` covering: ordered-by-default for both `Stream`
and `ParallelStream`, `unordered()` mutation and chaining (returns `self`,
composes with other intermediate ops), isolation across separate `Stream`
instances, and flag propagation across `.parallel()`/`.sequential()` mode
switches (both directions, with and without `unordered()` called). See
`openspec/changes/add-stream-unordered`.
