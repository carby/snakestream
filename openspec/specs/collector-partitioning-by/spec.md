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
downstream)` form, where each partition's bucketed elements are reduced via
`downstream` (any existing `collector.py` collector factory's returned
closure) instead of being left as a plain list, matching Java's
`Collectors.partitioningBy(Predicate predicate, Collector downstream)`.

#### Scenario: downstream collector reduces each partition
- **WHEN** `Stream.of([1, 2, 3, 4, 5]).collect(partitioning_by(lambda x: x % 2 == 0, counting()))` is called
- **THEN** the result is `{True: 2, False: 3}`

#### Scenario: downstream still runs on an empty partition
- **WHEN** `Stream.of([1, 3, 5]).collect(partitioning_by(lambda x: x % 2 == 0, counting()))` is called
- **THEN** the result is `{True: 0, False: 3}`, with `downstream` invoked over the empty `True` partition
