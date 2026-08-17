## Purpose

Comparator-based extremum collectors for use with `Stream.collect()`,
mirroring Java's `Collectors.min_by(Comparator)`/`max_by(Comparator)` statics.

## Requirements

### Requirement: `min_by(comparator)`/`max_by(comparator)` collector factories
`collector.py` SHALL provide `min_by(comparator)` and `max_by(comparator)`
functions, each returning a collector — an `async def` callable accepting an
`AsyncGenerator[T, None]` and returning `T | None` — usable with
`Stream.collect(collector)`. `comparator` follows the same 3-way-int
`Comparator` contract as `Stream.min`/`max` (negative if the first arg orders
before the second, zero if equal, positive if after), and may be sync or
async. `min_by` selects the element that never compares after any other
element seen so far (Java `Collectors.min_by` = "smallest according to
comparator"); `max_by` selects the element that never compares before any
other element seen so far.

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
