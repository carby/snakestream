## Purpose

Partitioning collector for use with `Stream.collect()`, mirroring Java's
`Collectors.partitioningBy(...)` overloads.

## Requirements

### Requirement: `partitioning_by(predicate)` collector factory (no downstream)
`collector.py` SHALL provide a `partitioning_by(predicate)` form — called
with no `downstream` — returning a collector that splits each pulled
element into a `True`/`False` bucket per `predicate(element)` (sync or
async) and returns `dict[bool, list[T]]` with exactly the two keys `True`
and `False` always present, matching Java's
`Collectors.partitioningBy(Predicate predicate)` (which defaults its
downstream to `toList()`).

#### Scenario: splits elements into true/false lists
- **WHEN** `Stream.of([1, 2, 3, 4, 5]).collect(partitioning_by(lambda x: x % 2 == 0))` is called
- **THEN** the result is `{True: [2, 4], False: [1, 3, 5]}`

#### Scenario: empty stream still yields both keys with empty lists
- **WHEN** `Stream.of([]).collect(partitioning_by(lambda x: True))` is called
- **THEN** the result is `{True: [], False: []}`

#### Scenario: one empty partition still appears as a key
- **WHEN** `Stream.of([1, 2, 3]).collect(partitioning_by(lambda x: x > 100))` is called
- **THEN** the result is `{True: [], False: [1, 2, 3]}`

#### Scenario: async predicate is awaited
- **WHEN** `partitioning_by(predicate)` is given an async `predicate`
- **THEN** the result is computed correctly, with `predicate` awaited via the same dispatch used elsewhere in the library

### Requirement: `partitioning_by(predicate, downstream)` composes a downstream collector
`collector.py` SHALL provide the 2-arg `partitioning_by(predicate,
downstream)` form, where `downstream` is a `Collector` and each partition's
elements are accumulated into that collector's own container instead of being
left as a plain list — matching Java's
`Collectors.partitioningBy(Predicate predicate, Collector downstream)`. The
default `downstream` SHALL remain the list-building collector, so the 1-arg
form's `dict[bool, list[T]]` result is unchanged.

Both partitions' containers SHALL be created up front, so an empty partition
still finishes to the downstream collector's empty-input result rather than
being absent. Passing a callable that is not a `Collector` as `downstream`
SHALL raise `StreamBuildException`.

#### Scenario: downstream collector reduces each partition
- **WHEN** `Stream.of([1, 2, 3, 4, 5]).collect(partitioning_by(lambda x: x % 2 == 0, counting()))` is called
- **THEN** the result is `{True: 2, False: 3}`

#### Scenario: downstream still runs on an empty partition
- **WHEN** `Stream.of([1, 3, 5]).collect(partitioning_by(lambda x: x % 2 == 0, counting()))` is called
- **THEN** the result is `{True: 0, False: 3}`, the empty `True` partition finishing to the downstream collector's empty-input result

#### Scenario: each partition gets its own downstream container
- **WHEN** `partitioning_by(predicate, downstream)` is used with a `downstream` whose container is mutable
- **THEN** the two partitions never share a container

#### Scenario: a non-Collector downstream is rejected
- **WHEN** `partitioning_by(predicate, downstream)` is given a plain callable as `downstream`
- **THEN** `StreamBuildException` is raised

### Requirement: `partitioning_by()` derives `UNORDERED` from its downstream

The collector returned by `partitioning_by(predicate, downstream)` SHALL
declare `Characteristics.UNORDERED` when, and only when, `downstream` declares
it.

The derivation SHALL rest on `partitioning_by()`'s own structure rather than on
`grouping_by()`'s. Both partitions are created before any element is
accumulated, so the result is always a two-key mapping carrying the same two
keys in the same order over any input, including an empty stream. No part of
the result depends on encounter order except the value collected into each
partition, and that dependence is the downstream's characteristic.

The rule SHALL be the same one `mapping()` and `collecting_and_then()` already
apply, and SHALL compose through nesting.

Java specifies nothing about `Collectors.partitioningBy()`'s characteristics,
so the derivation diverges from no documented contract.

#### Scenario: Partitioning into an unordered downstream is unordered
- **WHEN** the collector returned by `partitioning_by(p, to_set())` is asked
  for its characteristics
- **THEN** `UNORDERED` is present

#### Scenario: Partitioning into an ordered downstream is not unordered
- **WHEN** the collector returned by `partitioning_by(p, to_list())` is asked
  for its characteristics
- **THEN** `UNORDERED` is absent

#### Scenario: The default downstream is ordered
- **WHEN** the collector returned by `partitioning_by(p)` — taking the default
  downstream — is asked for its characteristics
- **THEN** `UNORDERED` is absent, because the default collects each partition
  into a list

#### Scenario: Derivation composes through nesting
- **WHEN** the collector returned by
  `partitioning_by(p, mapping(str, to_set()))` is asked for its characteristics
- **THEN** `UNORDERED` is present, derived through the adapter to the innermost
  downstream

#### Scenario: The two-key result is unaffected by the derivation
- **WHEN** a stream is collected with `partitioning_by(p, to_set())`, including
  an empty stream
- **THEN** the result carries exactly the two keys `True` and `False`, in that
  order, as it does without the derivation

#### Scenario: An unordered partitioning skips the delivery barrier
- **WHEN** an ordered racing pipeline is collected with
  `partitioning_by(p, to_set())`
- **THEN** the collected mapping is correct and no reorder barrier is engaged

### Requirement: `partitioning_by()` derives its combiner from its downstream

`partitioning_by()`'s collector SHALL declare a `combiner` only where its
downstream collector declares one, merging the `True` and `False` buckets of
two partial results by calling the downstream's own combiner on each bucket
pair - both buckets always exist (seeded in the supplier), so there is no
present-in-only-one-side case here, unlike `grouping_by()`'s arbitrary key
set. Where the downstream declares no combiner, `partitioning_by()`'s
collector SHALL declare none either.

#### Scenario: Parallel result over several batches matches sequential, combinable downstream
- **WHEN** a source spanning more than one batch is collected with `partitioning_by(predicate, counting())` under `.parallel()`
- **THEN** the result equals the sequential result

#### Scenario: A non-combinable downstream declares no combiner
- **WHEN** `partitioning_by(predicate, summing_double(mapper)).combiner` is read
- **THEN** it is `None`
