## Why

Snakestream's `collect()` only supports Java's single-arg `collect(Collector)` form. Java Stream also defines the 3-arg mutable-reduction overload, `collect(Supplier<R>, BiAccumulator<R,T>, BiCombiner<R,R>)`, which builds a result container directly from a supplier/accumulator pair instead of requiring a separate `Collector` object — e.g. `stream.collect(list, list.append, list.extend)`. This is roadmap item #1 (Now bucket): no blockers, independent Java-parity addition.

## What Changes

- Add a `collect(supplier, accumulator, combiner)` overload to `Stream.collect()` (`stream.py`), alongside the existing `collect(collector)` single-arg form.
- `supplier` is called with no arguments to create a fresh mutable container; `accumulator` is called once per pulled element as `accumulator(container, element)` to fold the element into the container; the container is returned once the composed generator is exhausted.
- Both `supplier` and `accumulator` may be sync or async, dispatched via the existing `_maybe_await` helper, matching every other user-supplied callable in the codebase.
- `combiner` is accepted (matching Java's signature, and reserved for a possible future partitioned-parallel execution model) but is not invoked: snakestream's `collect()` — like its existing `reduce()` — always folds over one single composed `AsyncGenerator`, sequential or parallel, with no independent partitions to merge. This is documented explicitly rather than left implicit.
- Add `Supplier` and `BiConsumer` type aliases to `type.py`, following the project's convention that composite/callable type shapes used in public signatures live there.

## Capabilities

### New Capabilities
- `mutable-reduction-collect`: the 3-arg `collect(supplier, accumulator, combiner)` terminal operation and its supplier/accumulator/combiner contract.

### Modified Capabilities
(none — the existing single-arg `collect(collector)` behavior is unchanged)

## Impact

- `src/snakestream/stream.py`: `Stream.collect()` gains an `@overload` pair (mirroring the existing `reduce()` pattern) and a runtime branch dispatching on arg count/shape.
- `src/snakestream/type.py`: new `Supplier`, `BiConsumer` aliases.
- New tests exercising sync/async supplier and accumulator, an empty stream, and `ParallelStream` (asserting `combiner` is never called and the result reflects the racing branches' interleaved contributions to one shared container).
- No breaking changes; purely additive overload.
