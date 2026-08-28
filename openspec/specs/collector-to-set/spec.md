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

### Requirement: `to_set()` declares `UNORDERED`

The collector returned by `to_set()` SHALL declare the `UNORDERED`
characteristic, matching Java, where `Collectors.toSet()` is the one
non-concurrent factory in `Collectors` whose documentation declares it — the
concurrent `groupingByConcurrent()` and `toConcurrentMap()` declare it too.

The declaration SHALL be true of the collector's behaviour and not merely
asserted: a `set` compares equal to another `set` with the same members
irrespective of the order in which either was built, so collecting any two
orderings of the same elements SHALL produce equal sets.

The justification SHALL rest on that equality and SHALL NOT rest on a claim
that a `set` retains no record of the order its members were added in. That
claim is false of the runtime — two equal sets built from the same elements in
different orders may iterate in different orders — and `UNORDERED` promises
equality, not iteration order (see the `collector-protocol` capability).

#### Scenario: to_set() reports UNORDERED
- **WHEN** the collector returned by `to_set()` is asked for its characteristics
- **THEN** `UNORDERED` is present

#### Scenario: The declaration matches the behaviour
- **WHEN** two streams carrying the same elements in different orders are each
  collected with `to_set()`
- **THEN** the two results are equal

#### Scenario: Collectors that observe order do not declare it
- **WHEN** the collectors returned by `to_list()` and `joining()` are asked for
  their characteristics
- **THEN** `UNORDERED` is absent from both, because each produces a result whose
  element order reflects the order it was fed
