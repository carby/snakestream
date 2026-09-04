## MODIFIED Requirements

### Requirement: `combiner` is invoked where a collection partitions

A `Collector`'s `combiner` SHALL be accepted, and SHALL be invoked to merge
two partial accumulations exactly when the parallel executor partitions the
collection it drives — governed by the partition protocol (`sink-protocol`)
and the merge rule (`parallel-reduction`). A collection that does not
partition — because `combiner` is `None`, because the executor is
sequential, or because an op in the chain needs a global view — SHALL fold
every element into a single container, exactly as before this requirement
changed, and SHALL NOT invoke `combiner`.

`to_list()` gained a combiner as part of this change (`collectors.py`'s leaf
combiners); it is no longer an example of a collector whose combiner is
never invoked.

A `Collector`'s own `combiner` follows Java's `Collector.combiner()`
convention — a `BinaryOperator<A>` returning the merged container — but the
merge mechanism also accepts a `None` return, read as "the container was
mutated in place": the three-argument `collect(supplier, accumulator,
combiner)` overload builds a plain `Collector` and drives it through the
same mechanism, and that surface's own `combiner` follows Java's other
convention, a mutating `BiConsumer<R,R>` (`mutable-reduction-collect`).

#### Scenario: The combiner is not called on a sequential stream
- **WHEN** a `Collector` whose combiner raises on call collects a sequential stream
- **THEN** the collection succeeds and the combiner is never called

#### Scenario: The combiner is not called when the collector supplies none
- **WHEN** a `Collector` constructed with no `combiner` collects a `.parallel()` stream
- **THEN** the collection succeeds, accumulating serially into one container, exactly as before

#### Scenario: The combiner is called on a partitioning parallel collection
- **WHEN** a `Collector` supplying a `combiner` collects a `.parallel()` stream whose source spans more than one batch, with nothing in the chain requiring a global view
- **THEN** the combiner is invoked at least once, and the result equals the sequential result
