## Purpose

A downstream-adapting collector that maps each element before handing it to
another collector, mirroring Java's `Collectors.mapping(mapper, downstream)`.

## Requirements

### Requirement: `mapping()` collector factory
`collector.py` SHALL provide a `mapping(mapper, downstream)` function that
returns a `Collector`. For each element pulled from the stream, it SHALL
apply `mapper` (sync or async) to the element and feed the mapped value to
`downstream`'s accumulator, then produce `downstream`'s finished result.
`downstream` SHALL be a `Collector`; passing anything else SHALL raise
`StreamBuildException`.

#### Scenario: Mapped values are collected by the downstream collector
- **WHEN** `Stream.of(["a", "bb", "ccc"]).collect(mapping(len, to_list()))` is called
- **THEN** the result is `[1, 2, 3]`

#### Scenario: Async mapper is awaited
- **WHEN** `Stream.of([1, 2, 3]).collect(mapping(async_double, to_list()))` is called with an async mapper doubling its input
- **THEN** the result is `[2, 4, 6]`

#### Scenario: Empty stream yields the downstream's empty result
- **WHEN** `Stream.of([]).collect(mapping(len, to_list()))` is called
- **THEN** the result is `[]`

#### Scenario: Mapping composes with a reducing downstream
- **WHEN** `Stream.of(["a", "bb", "ccc"]).collect(mapping(len, counting()))` is called
- **THEN** the result is `3`

#### Scenario: Non-Collector downstream is rejected
- **WHEN** `mapping(len, lambda c: c)` is called with a plain callable as `downstream`
- **THEN** `StreamBuildException` is raised
