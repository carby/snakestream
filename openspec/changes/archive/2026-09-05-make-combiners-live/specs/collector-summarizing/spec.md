## ADDED Requirements

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
