## ADDED Requirements

### Requirement: `to_collection()` declares a combiner

`to_collection(collection_supplier)`'s collector SHALL declare a `combiner`
that merges two partial containers by adding every element of the second
into the first, one at a time (`add()` per element) - the one operation
available generically over the `_SupportsAdd` protocol this factory is typed
against, since it guarantees `add()` but not a bulk merge. Holds for any
container this factory is used with in practice (`list`, `set`, `deque`, and
any other iterable-plus-`add()` type).

#### Scenario: Parallel result over several batches matches sequential
- **WHEN** a source spanning more than one batch is collected with `to_collection(set)` under `.parallel()`
- **THEN** the result equals the sequential result
