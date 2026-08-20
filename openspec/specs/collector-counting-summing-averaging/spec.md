## Purpose

Numeric reducing collectors for use with `Stream.collect()`, mirroring
Java's `Collectors.counting()`, `summingInt`/`summingLong`/`summingDouble`,
and `averagingInt`/`averagingLong`/`averagingDouble` statics.

## Requirements

### Requirement: `counting()` collector factory
`collector.py` SHALL provide a `counting()` function that returns a
`Collector` counting the elements it accumulates and finishing to that `int`
count — usable with `Stream.collect(collector)`.

#### Scenario: Non-empty stream is counted
- **WHEN** `Stream.of([1, 2, 3]).collect(counting())` is called
- **THEN** the result is `3`

#### Scenario: Empty stream counts to zero
- **WHEN** `Stream.of([]).collect(counting())` is called
- **THEN** the result is `0`

### Requirement: `summing_int()`/`summing_long()` collector factories
`collector.py` SHALL provide `summing_int(mapper)` and `summing_long(mapper)`
functions, each returning a collector that maps every pulled element via
`mapper` (sync or async) and returns the `int` sum of the mapped values.
Both functions SHALL behave identically, mirroring Java's `Collectors
.summingInt`/`summingLong` under separate names despite Python having no
`int`/`long` distinction.

#### Scenario: summing_int sums mapped values
- **WHEN** `Stream.of(["a", "bb", "ccc"]).collect(summing_int(len))` is called
- **THEN** the result is `6`

#### Scenario: summing_long behaves identically to summing_int
- **WHEN** `Stream.of(["a", "bb", "ccc"]).collect(summing_long(len))` is called
- **THEN** the result is `6`

#### Scenario: summing_int on an empty stream returns zero
- **WHEN** `Stream.of([]).collect(summing_int(len))` is called
- **THEN** the result is `0`

#### Scenario: async mapper is awaited
- **WHEN** `Stream.of([1, 2, 3]).collect(summing_int(async_double))` is called with an async mapper doubling its input
- **THEN** the result is `12`

### Requirement: `summing_double()` collector factory
`collector.py` SHALL provide a `summing_double(mapper)` function returning a
collector that maps every pulled element via `mapper` (sync or async) and
returns the `float` sum of the mapped values, coercing each mapped value to
`float` before accumulating.

#### Scenario: summing_double sums as float
- **WHEN** `Stream.of([1, 2, 3]).collect(summing_double(lambda x: x))` is called
- **THEN** the result is `6.0` and is a `float`

#### Scenario: summing_double on an empty stream returns 0.0
- **WHEN** `Stream.of([]).collect(summing_double(lambda x: x))` is called
- **THEN** the result is `0.0`

### Requirement: `averaging_int()`/`averaging_long()`/`averaging_double()` collector factories
`collector.py` SHALL provide `averaging_int(mapper)`, `averaging_long(mapper)`,
and `averaging_double(mapper)` functions, each returning a collector that
maps every pulled element via `mapper` (sync or async) and returns the
arithmetic mean of the mapped values as a `float`. All three SHALL behave
identically, mirroring Java's `Collectors.averagingInt`/`averagingLong`/
`averagingDouble` under separate names despite Python having no `int`/
`long`/`double` distinction. An empty stream SHALL yield `0.0`, matching
Java's `Collectors.averaging*` javadocs.

#### Scenario: averaging_int computes the mean
- **WHEN** `Stream.of([1, 2, 3, 4]).collect(averaging_int(lambda x: x))` is called
- **THEN** the result is `2.5`

#### Scenario: averaging_long behaves identically to averaging_int
- **WHEN** `Stream.of([1, 2, 3, 4]).collect(averaging_long(lambda x: x))` is called
- **THEN** the result is `2.5`

#### Scenario: averaging_double behaves identically to averaging_int
- **WHEN** `Stream.of([1, 2, 3, 4]).collect(averaging_double(lambda x: x))` is called
- **THEN** the result is `2.5`

#### Scenario: averaging on an empty stream returns 0.0
- **WHEN** `Stream.of([]).collect(averaging_int(lambda x: x))` is called
- **THEN** the result is `0.0`
