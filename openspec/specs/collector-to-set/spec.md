## Purpose

`set`-building collector for use with `Stream.collect()`, mirroring Java's
`Collectors.toSet()`.

## Requirements

### Requirement: `to_set()` collector factory
`collector.py` SHALL provide a `to_set()` collector factory returning a
collector that builds a `set` from the composed stream's elements, matching
Java's `Collectors.toSet()`.

#### Scenario: builds a set from stream elements
- **WHEN** `Stream.of([1, 2, 2, 3]).collect(to_set())` is called
- **THEN** the result is `{1, 2, 3}`

#### Scenario: empty stream yields an empty set
- **WHEN** `Stream.of([]).collect(to_set())` is called
- **THEN** the result is `set()`

#### Scenario: takes no arguments
- **WHEN** `to_set()` is called
- **THEN** it accepts no arguments, matching Java's zero-arg `Collectors.toSet()`
</content>
