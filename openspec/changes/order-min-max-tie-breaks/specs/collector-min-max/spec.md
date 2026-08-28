## ADDED Requirements

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
