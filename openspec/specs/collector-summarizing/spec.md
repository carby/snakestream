## Purpose

Collectors that summarize the mapped numeric values of a stream into a
single count/sum/min/max/average result, mirroring Java's
`Collectors.summarizingInt`/`summarizingLong`/`summarizingDouble` and their
`IntSummaryStatistics`/`LongSummaryStatistics`/`DoubleSummaryStatistics`
result types.

## Requirements

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

### Requirement: `summarizing_int()` and `summarizing_long()` declare `UNORDERED`

The collectors returned by `summarizing_int(mapper)` and
`summarizing_long(mapper)` SHALL declare the `UNORDERED` characteristic.

The declaration SHALL rest on the equality of the produced `SummaryStatistics`
and on nothing weaker. `SummaryStatistics` compares by value across all of
`count`, `sum`, `min`, `max` and `average`, so the declaration holds only if
every field is order-invariant, and over `int` inputs each is: `count` and `sum`
are exact and associative, `min` and `max` select a *value* rather than an
element identity — so there is no tie to break, unlike `min_by`/`max_by`, which
return an element and are excluded by the `collector-min-max` capability — and
`average` is that exact `sum` divided by that exact `count`.

#### Scenario: summarizing_int() and summarizing_long() report UNORDERED
- **WHEN** the collectors returned by `summarizing_int(mapper)` and
  `summarizing_long(mapper)` are asked for their characteristics
- **THEN** `UNORDERED` is present on both

#### Scenario: Every field of the result is order-invariant
- **WHEN** two streams carrying the same integer elements in different orders
  are each collected with `summarizing_int(mapper)`
- **THEN** the two `SummaryStatistics` results compare equal under `==`,
  including their `min`, `max` and `average` fields

#### Scenario: The mark removes the delivery barrier under racing
- **WHEN** an ordered racing pipeline is collected with `summarizing_int(mapper)`
- **THEN** no reorder barrier is engaged and the result equals the sequential
  pipeline's result

### Requirement: `summarizing_double()` SHALL NOT declare `UNORDERED`

The collector returned by `summarizing_double(mapper)` SHALL NOT declare the
`UNORDERED` characteristic, and SHALL NOT be marked by any later change.

Its `sum` accumulates in floating point, where addition is not associative, so
two orderings of the same elements can produce sums — and therefore averages —
that compare unequal under `==`. That its `count`, `min` and `max` fields are
order-invariant does not rescue the declaration: `SummaryStatistics` compares by
value across all fields, so one order-sensitive field makes the whole result
order-sensitive.

#### Scenario: summarizing_double() reports no UNORDERED
- **WHEN** the collector returned by `summarizing_double(mapper)` is asked for
  its characteristics
- **THEN** `UNORDERED` is absent

#### Scenario: It is fed in encounter order under racing
- **WHEN** an ordered racing pipeline is collected with
  `summarizing_double(mapper)`
- **THEN** the delivery barrier is engaged and the result equals the sequential
  pipeline's result exactly

### Requirement: `summarizing_int()`/`summarizing_long()` declare a combiner

`summarizing_int()`'s and `summarizing_long()`'s collectors SHALL each
declare a `combiner` that merges two partial `SummaryStatistics` accumulations:
`count` and `sum` add, `min` and `max` each take whichever side's value is
smaller/larger, on the exact int/long fields these two factories accumulate.

#### Scenario: Parallel result over several batches matches sequential
- **WHEN** a source spanning more than one batch is collected with `summarizing_int(mapper)` under `.parallel()`
- **THEN** the result equals the sequential result

### Requirement: `summarizing_double()` permanently declines a combiner

`summarizing_double()`'s collector SHALL declare no `combiner`. Its `sum`
field accumulates into a `float` running total, the same reason
`summing_double()` is excluded; one order-sensitive field is enough to make
the whole `SummaryStatistics` compare unequal under a different
partitioning, however exact `count`/`min`/`max` are beside it.

#### Scenario: summarizing_double declares no combiner
- **WHEN** `summarizing_double(mapper).combiner` is read
- **THEN** it is `None`, and a `.parallel()` collection with it is not partitioned
