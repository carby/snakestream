## ADDED Requirements

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
