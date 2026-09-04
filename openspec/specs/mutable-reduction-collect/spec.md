## Purpose

Defines the contract for `Stream.collect(supplier, accumulator, combiner)`, the 3-arg mutable-reduction overload of `collect()` that builds a result container directly from a supplier/accumulator pair, mirroring Java's `Stream.collect(Supplier<R>, BiConsumer<R,? super T>, BiConsumer<R,R>)`. Exists alongside, and does not change, the existing single-arg `collect(collector)` form. Applies identically under the sequential and fork-join executors.

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
- **THEN** behavior is identical to before this change — `collector` is invoked directly against the stream's composed pipeline

### Requirement: `combiner` is invoked where the collection partitions

The third argument, `combiner`, SHALL be accepted, and SHALL be invoked to
merge two batches' independently accumulated containers whenever the parallel
executor partitions the collection — governed by the partition protocol
(`sink-protocol`) and the merge rule (`parallel-reduction`). `combiner` SHALL
NOT be invoked under the sequential executor, matching
`reduce(identity, accumulator, combiner)`'s posture.

`combiner` SHALL be accepted in either of the two conventions Java itself
uses across its two combiner-bearing surfaces: as a `BiConsumer<R,R>` that
mutates its first argument and returns nothing — matching
`Stream.collect(Supplier, BiConsumer, BiConsumer)` exactly, whose own
documented example is `List::addAll` — or as a function that returns the
merged container, matching `Collector.combiner()`'s `BinaryOperator<A>`. A
`None` return SHALL be read as "the container was mutated in place" rather
than as the new container, so an existing `list.extend`-style combiner
requires no change now that `combiner` is live.

#### Scenario: `combiner` is never called, sequential
- **WHEN** `Stream.of([1, 2, 3]).collect(list, list.append, combiner)` is called with a `combiner` that records its own invocations
- **THEN** the result is `[1, 2, 3]` and `combiner` was never called

#### Scenario: A combiner returning the merged container merges correctly, parallel
- **WHEN** a 3-arg `collect()` call whose `combiner` returns the merged container is made on a `.parallel()` stream whose source spans more than one batch
- **THEN** the returned container holds every source element, `combiner` was called at least once, and the result equals the sequential result

#### Scenario: A combiner that mutates in place and returns None also merges correctly
- **WHEN** a 3-arg `collect()` call is made with `list.extend` as `combiner` — mutating its first argument and returning `None` — on a `.parallel()` stream whose source spans more than one batch
- **THEN** the returned container holds every source element, and the result equals the sequential result
