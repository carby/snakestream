## ADDED Requirements

### Requirement: `counting()`, `summing_int()` and `summing_long()` declare a combiner

`counting()`'s collector SHALL declare a `combiner` that adds two partial
counts. `summing_int()`'s and `summing_long()`'s collectors SHALL each
declare a `combiner` that adds two partial integer totals. Integer addition
is exact and associative, so partitioning changes nothing about the result -
the same ground these three already declare `UNORDERED` on.

#### Scenario: Parallel counting over several batches matches sequential
- **WHEN** a source spanning more than one batch is collected with `counting()` under `.parallel()`
- **THEN** the result equals the sequential result

#### Scenario: Parallel summing_int over several batches matches sequential
- **WHEN** a source spanning more than one batch is collected with `summing_int(mapper)` under `.parallel()`
- **THEN** the result equals the sequential result

### Requirement: The floating-point numeric collectors permanently decline a combiner

`summing_double()` and **all three** of `averaging_int()`/`averaging_long()`/
`averaging_double()` SHALL declare no `combiner`. Each accumulates into a
`float` running total (`summing_double`'s `_SumBox.total`; every `averaging_*`
shares one `_averaging()` whose `_AvgBox.total` is a `float`), and float
addition is not associative: partitioning would change the summation order
and so the result. `averaging_int()` and `averaging_long()` are excluded
despite their integral element types, because the accumulator they share
with `averaging_double()` divides a `float` regardless of what is mapped
into it. This is a stronger, permanent exclusion — not merely an
undeclared trait a later pass might add.

#### Scenario: summing_double declares no combiner
- **WHEN** `summing_double(mapper).combiner` is read
- **THEN** it is `None`, and a `.parallel()` collection with it is not partitioned - its result is bit-for-bit identical to the sequential one

#### Scenario: averaging_int declares no combiner despite an integral element type
- **WHEN** `averaging_int(mapper).combiner` is read
- **THEN** it is `None`

#### Scenario: averaging_long and averaging_double declare no combiner
- **WHEN** `averaging_long(mapper).combiner` and `averaging_double(mapper).combiner` are each read
- **THEN** both are `None`
