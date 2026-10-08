+++
id = "three-argument-collect"
title = "Added `Stream.collect(supplier, accumulator, combiner)`"
filed = 2026-08-17
closed = 2026-08-17
outcome = "shipped"
+++

Added `Stream.collect(supplier, accumulator, combiner)` (`stream.py`) —
Java's 3-arg mutable-reduction overload of `collect()`, alongside the
existing single-arg `collect(collector)` form. Implemented as an
`@overload` pair dispatching on arg count, mirroring the precedent already
set by `reduce()`'s identity/no-identity overloads: `supplier` is called
once with no arguments to produce a fresh mutable container, `accumulator`
is called once per pulled element as `accumulator(container, element)`,
and both may be sync or async, dispatched via the existing `_maybe_await`
helper. `combiner` is accepted for signature parity with Java but is
never invoked — `collect()`, like the already-shipped `reduce()`, always
folds over a single composed `AsyncGenerator` (sequential or parallel)
with no independently-accumulated partitions to merge, so wiring up a real
combine step is tracked separately in **Later** below, alongside the
`.parallel()`/`PROCESSES` semantics decision it's blocked on. Added new
`Supplier`/`BiConsumer` type aliases to `type.py`. Added 5 new tests in
`tests/test_collect.py`: sync and async supplier/accumulator, an empty
stream, and `combiner`-never-called coverage for both sequential `Stream`
and `ParallelStream`. Updated README's parity table. No breaking changes.
See `openspec/changes/archive/2026-08-17-add-collect-supplier-accumulator-combiner`.
