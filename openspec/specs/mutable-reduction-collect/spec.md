## Purpose

Defines the contract for `Stream.collect(supplier, accumulator, combiner)`, the 3-arg mutable-reduction overload of `collect()` that builds a result container directly from a supplier/accumulator pair, mirroring Java's `Stream.collect(Supplier<R>, BiConsumer<R,? super T>, BiConsumer<R,R>)`. Exists alongside, and does not change, the existing single-arg `collect(collector)` form. Applies identically to `Stream` (sequential) and `ParallelStream` (parallel) composition.

## Requirements

### Requirement: 3-arg mutable-reduction `collect(supplier, accumulator, combiner)`
`Stream.collect()` SHALL accept an overload taking exactly three positional arguments — `supplier`, `accumulator`, `combiner` — as an alternative to the existing single-arg `collect(collector)` form. `supplier` SHALL be called with no arguments exactly once to produce a fresh mutable result container. `accumulator` SHALL be called once per element pulled from the composed stream, as `accumulator(container, element)`, folding that element into the container. The call SHALL return the container once the composed stream is exhausted. Both `supplier` and `accumulator` MAY be sync or async callables, dispatched consistently with every other user-supplied callable in the codebase (`_maybe_await`).

#### Scenario: Sync supplier and accumulator build a list
- **WHEN** `Stream.of([1, 2, 3]).collect(list, list.append, list.extend)` is called
- **THEN** the result is `[1, 2, 3]`

#### Scenario: Async supplier and accumulator are awaited
- **WHEN** `collect()` is called with an `async def` supplier and an `async def` accumulator
- **THEN** both are awaited and the returned container reflects every element folded in via the accumulator

#### Scenario: Empty stream still returns a container
- **WHEN** `collect(supplier, accumulator, combiner)` is called on a stream with no elements
- **THEN** `supplier` is still called once and its untouched container is returned, with `accumulator` never called

#### Scenario: Existing single-arg `collect(collector)` is unaffected
- **WHEN** `collect(collector)` is called with exactly one positional argument
- **THEN** behavior is identical to before this change — `collector(self._compose())` is invoked directly

### Requirement: `combiner` is accepted but not invoked
The third argument, `combiner`, SHALL be accepted for signature parity with Java's `Stream.collect(Supplier, BiConsumer, BiConsumer)` but SHALL NOT be called by this implementation, on `Stream` or `ParallelStream`. Both fold over a single composed `AsyncGenerator` with no independently-accumulated partitions to merge, matching the existing `reduce(identity, accumulator)` behavior under `.parallel()`.

#### Scenario: `combiner` is never called, sequential
- **WHEN** `Stream.of([1, 2, 3]).collect(list, list.append, combiner)` is called with a `combiner` that records its own invocations
- **THEN** the result is `[1, 2, 3]` and `combiner` was never called

#### Scenario: `combiner` is never called, parallel
- **WHEN** the same 3-arg `collect()` call is made on a `ParallelStream` instance
- **THEN** the returned container holds all source elements (order not guaranteed) and `combiner` was never called
