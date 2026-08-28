## Purpose

Comparator-based extremum collectors for use with `Stream.collect()`,
mirroring Java's `Collectors.min_by(Comparator)`/`max_by(Comparator)` statics.

## Requirements

### Requirement: `min_by(comparator)`/`max_by(comparator)` collector factories
`collector.py` SHALL provide `min_by(comparator)` and `max_by(comparator)`
functions, each returning a `Collector` that accumulates the running extremum
and finishes to `T | None` — usable with `Stream.collect(collector)`.
`comparator` follows the same 3-way-int `Comparator` contract as
`Stream.min`/`max` (negative if the first arg orders before the second, zero
if equal, positive if after), and may be sync or async. `min_by` selects the
element that never compares after any other element seen so far (Java
`Collectors.min_by` = "smallest according to comparator"); `max_by` selects
the element that never compares before any other element seen so far.

The tie-break and the comparator-result-type guard SHALL be the same ones
`Stream.min`/`max` apply, not an independent reimplementation of them.

#### Scenario: min_by selects the smallest element
- **WHEN** `Stream.of([3, 1, 2]).collect(min_by(lambda a, b: a - b))` is called
- **THEN** the result is `1`

#### Scenario: max_by selects the largest element
- **WHEN** `Stream.of([3, 1, 2]).collect(max_by(lambda a, b: a - b))` is called
- **THEN** the result is `3`

#### Scenario: empty stream yields None
- **WHEN** `Stream.of([]).collect(min_by(lambda a, b: a - b))` is called
- **THEN** the result is `None`

#### Scenario: tie keeps the first of equal elements
- **WHEN** a stream of two equal-under-comparator but distinct objects is collected with `min_by` (or `max_by`)
- **THEN** the first of the two encountered is returned, matching `Stream.min`/`max`'s existing tie-break

#### Scenario: async comparator is awaited
- **WHEN** `min_by`/`max_by` is given an `async def` comparator
- **THEN** the result is computed correctly, with the comparator awaited via the same dispatch used elsewhere in the library

#### Scenario: bool-returning comparator raises TypeError
- **WHEN** `min_by`/`max_by` is given a comparator that returns a `bool` (e.g. `lambda a, b: a > b`) instead of an `int`
- **THEN** a `TypeError` is raised, matching `Stream.min`/`max`/`sorted`'s existing comparator-contract guard
### Requirement: min_by()/max_by() do not declare UNORDERED
`min_by()` and `max_by()` SHALL NOT declare `Characteristics.UNORDERED`. Which
of two equal-comparing distinguishable elements they return is an
encounter-order question, not an order-blind one, so on an ordered racing
pipeline `collect(min_by(c))` SHALL receive its elements in encounter order and
SHALL return the earlier-encountered of two tied elements — the same element
`Stream.min()` returns for the same pipeline and comparator.

The two forms SHALL agree: for any pipeline and comparator, `Stream.min(c)` and
`collect(min_by(c))` SHALL return the same element, and likewise for `max`.
This holds on ordered pipelines by both taking the delivery barrier, and on
`unordered()` pipelines by both being released from it and both being
unspecified on a tie, per `comparator-contract`.

This SHALL remain true if the collectors Java leaves unmarked are later marked
`UNORDERED` on measurement: these two are excluded from that question by this
requirement rather than by convention.

#### Scenario: An ordered racing max_by() breaks ties in encounter order
- **WHEN** an ordered racing pipeline over records whose comparator keys tie is
  collected with `max_by(c)`
- **THEN** the result is the tied record earliest in encounter order, equal to
  the sequential result

#### Scenario: The collector form agrees with the stream form
- **WHEN** the same ordered racing pipeline is reduced once with `min(c)` and
  once with `collect(min_by(c))` over records whose comparator keys tie
- **THEN** both return the same record

#### Scenario: min_by() declares no characteristics
- **WHEN** `min_by(c).characteristics` and `max_by(c).characteristics` are read
- **THEN** neither contains `Characteristics.UNORDERED`
