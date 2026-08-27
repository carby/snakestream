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

### Requirement: `mapping()` carries its downstream's characteristics

The collector returned by `mapping(mapper, downstream)` SHALL declare exactly
the characteristics `downstream` declares, matching Java, where `mapping()`
derives its characteristics from the downstream collector rather than fixing
its own.

This follows from what `mapping()` is: it transforms each element on its way in
and then produces `downstream`'s result unchanged, so every trait of that
result is a trait of `downstream`. In particular, mapping into a downstream
that does not observe encounter order yields a collector that does not observe
it either, because the mapper is applied per element and cannot make the result
depend on position.

#### Scenario: Mapping into an unordered downstream is unordered
- **WHEN** the collector returned by `mapping(len, to_set())` is asked for its
  characteristics
- **THEN** `UNORDERED` is present

#### Scenario: Mapping into an ordered downstream is not unordered
- **WHEN** the collector returned by `mapping(len, to_list())` is asked for its
  characteristics
- **THEN** `UNORDERED` is absent

#### Scenario: Nested mapping derives through both levels
- **WHEN** the collector returned by `mapping(len, mapping(str, to_set()))` is
  asked for its characteristics
- **THEN** `UNORDERED` is present, derived from the innermost downstream
