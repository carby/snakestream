## Purpose

A result-adapting collector that runs a downstream collector's finished
result through an additional finisher, mirroring Java's
`Collectors.collectingAndThen(downstream, finisher)`.

## ADDED Requirements

### Requirement: `collecting_and_then()` collector factory
`collector.py` SHALL provide a `collecting_and_then(downstream, finisher)`
function that returns a `Collector`. It SHALL accumulate elements exactly as
`downstream` would, then apply `finisher` (sync or async) to `downstream`'s
finished result and return that as the overall result. `downstream` SHALL be
a `Collector`; passing anything else SHALL raise `StreamBuildException`.

#### Scenario: Finisher transforms the downstream's result
- **WHEN** `Stream.of([1, 2, 3]).collect(collecting_and_then(to_list, tuple))` is called
- **THEN** the result is `(1, 2, 3)`

#### Scenario: Async finisher is awaited
- **WHEN** `Stream.of([1, 2, 3]).collect(collecting_and_then(to_list, async_len))` is called with an async finisher returning the list's length
- **THEN** the result is `3`

#### Scenario: Composes with a downstream that already has its own finisher
- **WHEN** `Stream.of([1, 2, 3]).collect(collecting_and_then(counting(), lambda n: n * 10))` is called
- **THEN** the result is `30`

#### Scenario: Empty stream still runs the finisher
- **WHEN** `Stream.of([]).collect(collecting_and_then(to_list, tuple))` is called
- **THEN** the result is `()`

#### Scenario: Non-Collector downstream is rejected
- **WHEN** `collecting_and_then(lambda c: c, tuple)` is called with a plain callable as `downstream`
- **THEN** `StreamBuildException` is raised
