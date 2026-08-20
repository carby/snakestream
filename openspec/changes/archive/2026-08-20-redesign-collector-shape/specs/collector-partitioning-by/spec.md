## MODIFIED Requirements

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
