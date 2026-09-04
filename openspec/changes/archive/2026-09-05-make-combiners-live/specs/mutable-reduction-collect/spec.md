## MODIFIED Requirements

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
