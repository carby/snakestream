## Purpose

A generalized collector that accumulates stream elements into an
arbitrary caller-supplied container, mirroring Java's
`Collectors.toCollection(collectionSupplier)`.

## ADDED Requirements

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
