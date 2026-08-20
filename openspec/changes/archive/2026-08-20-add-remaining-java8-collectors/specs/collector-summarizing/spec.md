## Purpose

Collectors that summarize the mapped numeric values of a stream into a
single count/sum/min/max/average result, mirroring Java's
`Collectors.summarizingInt`/`summarizingLong`/`summarizingDouble` and their
`IntSummaryStatistics`/`LongSummaryStatistics`/`DoubleSummaryStatistics`
result types.

## ADDED Requirements

### Requirement: `SummaryStatistics` result type
`collector.py` SHALL provide a `SummaryStatistics` type with fields `count`
(`int`), `sum` (`int` or `float`), `min` (`int`, `float`, or `None`), `max`
(`int`, `float`, or `None`), and `average` (`float`). It SHALL be immutable.

#### Scenario: Fields are accessible by name
- **WHEN** a `SummaryStatistics` result is produced from `[1, 2, 3, 4]`
- **THEN** `.count == 4`, `.sum == 10`, `.min == 1`, `.max == 4`, `.average == 2.5`

### Requirement: `summarizing_int()`/`summarizing_long()`/`summarizing_double()` collector factories
`collector.py` SHALL provide `summarizing_int(mapper)`,
`summarizing_long(mapper)`, and `summarizing_double(mapper)` functions, each
returning a collector that maps every pulled element via `mapper` (sync or
async) and finishes to a `SummaryStatistics` over the mapped values. All
three SHALL behave identically apart from `summarizing_double` coercing
mapped values and `sum`/`min`/`max` to `float`, mirroring the existing
`summing_*`/`averaging_*` split between the int/long family and the double
family.

#### Scenario: Summary statistics over mapped values
- **WHEN** `Stream.of(["a", "bb", "ccc"]).collect(summarizing_int(len))` is called
- **THEN** the result's `count` is `3`, `sum` is `6`, `min` is `1`, `max` is `3`, and `average` is `2.0`

#### Scenario: summarizing_long behaves identically to summarizing_int
- **WHEN** `Stream.of([1, 2, 3]).collect(summarizing_long(lambda x: x))` is called
- **THEN** the result equals `Stream.of([1, 2, 3]).collect(summarizing_int(lambda x: x))`'s result

#### Scenario: summarizing_double coerces to float
- **WHEN** `Stream.of([1, 2, 3]).collect(summarizing_double(lambda x: x))` is called
- **THEN** the result's `sum`, `min`, and `max` are all `float` (`6.0`, `1.0`, `3.0`)

#### Scenario: Async mapper is awaited
- **WHEN** `Stream.of([1, 2, 3]).collect(summarizing_int(async_double))` is called with an async mapper doubling its input
- **THEN** the result's `sum` is `12`

#### Scenario: Empty stream yields a zeroed summary with no min/max
- **WHEN** `Stream.of([]).collect(summarizing_int(len))` is called
- **THEN** the result's `count` is `0`, `sum` is `0`, `min` is `None`, `max` is `None`, and `average` is `0.0`
