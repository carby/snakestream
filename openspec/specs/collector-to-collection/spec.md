## Purpose

A generalized collector that accumulates stream elements into an
arbitrary caller-supplied container, mirroring Java's
`Collectors.toCollection(collectionSupplier)`.

## Requirements

### Requirement: `to_collection()` collector factory
`collector.py` SHALL provide a `to_collection(collection_supplier)` function
that returns a `Collector`. It SHALL call `collection_supplier()` once to
create a fresh container, and add each pulled element to that container via
the container's `add` method, then return the container itself as the
result (no separate finisher).

#### Scenario: Elements are added to a fresh container per collection
- **WHEN** `Stream.of([1, 2, 3]).collect(to_collection(set))` is called
- **THEN** the result is `{1, 2, 3}`

#### Scenario: A custom container type is supported
- **WHEN** `Stream.of([3, 1, 2]).collect(to_collection(lambda: SortedContainer()))` is called with a container whose `add` keeps it sorted
- **THEN** the result reflects elements added in sorted order

#### Scenario: Each collection gets its own container
- **WHEN** the same `to_collection(list)` collector instance is used across two separate `collect()` calls
- **THEN** each call's result is an independent container, unaffected by the other call's elements

#### Scenario: Empty stream yields an empty container
- **WHEN** `Stream.of([]).collect(to_collection(list))` is called
- **THEN** the result is `[]`

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
