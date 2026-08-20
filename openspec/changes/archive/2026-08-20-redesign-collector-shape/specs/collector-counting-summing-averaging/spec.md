## MODIFIED Requirements

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
