+++
id = "second-terminal-wrong-results"
title = "Fixed two bugs that made a second terminal operation return wrong results"
filed = 2026-08-12
closed = 2026-08-12
outcome = "shipped"
+++

Fixed two compounding bugs that made a second terminal operation on the
same `Stream`/`ParallelStream` instance silently return wrong (usually
empty) results instead of repeating the first run's behavior. First,
`BaseStream._sequential()` (`base_stream.py`) was handed `self._chain`
directly and called `pop(0)` on it, draining the caller's own chain list
during `_compose()`; fixed by passing `self._chain[:]` (a copy) from
`_compose()` instead — matching the copy `ParallelStream._parallel()`
already made for its own branches, so both subclasses now honor the same
non-destructive contract. Second, `distinct()`/`limit()` (`stream.py`)
each built their `seen`/`size` state in the outer function that runs once
per `.distinct()`/`.limit()` call, rather than in the closure that runs
once per composition, so that state silently persisted across separate
compositions of the same chain; fixed by replacing the two closures with
small callable classes (`_DistinctOp`, `_LimitOp`) whose `__call__` takes
an optional external state and falls back to fresh per-call state via
their own `make_state()` when none is given — giving `Stream` (sequential)
fresh state on every composition by default. For `ParallelStream`, where
multiple racing branches must share one `seen`/`size` per composition to
stay globally correct (matching Java's guarantee that parallel `distinct`/
`limit` never silently degrade into a per-partition, unreconciled result,
even though it costs more to coordinate — see
`openspec/changes/fix-stream-rerun-state/design.md`), `_parallel()` now
builds one state map per composition via each op's `make_state()` and
passes the same map into every racing branch's `_sequential()` call.
Added regression tests covering: chain length unaffected by composition,
a second terminal op after the first, `distinct()`/`limit()` state not
leaking across separate `Stream`/`ParallelStream` instances or across
separate compositions of one instance, and parallel `distinct()`/`limit()`
staying globally correct (no cross-branch duplicates, no over-`limit()`)
across racing branches.
