## Purpose

A result-adapting collector that runs a downstream collector's finished
result through an additional finisher, mirroring Java's
`Collectors.collectingAndThen(downstream, finisher)`.

## Requirements

### Requirement: `collecting_and_then()` collector factory
`collector.py` SHALL provide a `collecting_and_then(downstream, finisher)`
function that returns a `Collector`. It SHALL accumulate elements exactly as
`downstream` would, then apply `finisher` (sync or async) to `downstream`'s
finished result and return that as the overall result. `downstream` SHALL be
a `Collector`; passing anything else SHALL raise `StreamBuildException`.

#### Scenario: Finisher transforms the downstream's result
- **WHEN** `Stream.of([1, 2, 3]).collect(collecting_and_then(to_list(), tuple))` is called
- **THEN** the result is `(1, 2, 3)`

#### Scenario: Async finisher is awaited
- **WHEN** `Stream.of([1, 2, 3]).collect(collecting_and_then(to_list(), async_len))` is called with an async finisher returning the list's length
- **THEN** the result is `3`

#### Scenario: Composes with a downstream that already has its own finisher
- **WHEN** `Stream.of([1, 2, 3]).collect(collecting_and_then(counting(), lambda n: n * 10))` is called
- **THEN** the result is `30`

#### Scenario: Empty stream still runs the finisher
- **WHEN** `Stream.of([]).collect(collecting_and_then(to_list(), tuple))` is called
- **THEN** the result is `()`

#### Scenario: Non-Collector downstream is rejected
- **WHEN** `collecting_and_then(lambda c: c, tuple)` is called with a plain callable as `downstream`
- **THEN** `StreamBuildException` is raised

### Requirement: `collecting_and_then()` carries its downstream's characteristics

The collector returned by `collecting_and_then(downstream, finisher)` SHALL
declare exactly the characteristics `downstream` declares, matching Java, where
`collectingAndThen()` derives from the downstream collector.

Accumulation is `downstream`'s unchanged, and `finisher` is applied once to the
finished result rather than per element, so it cannot introduce a dependence on
the order the elements arrived in. A collector that did not observe encounter
order does not begin to observe it by having its result transformed.

Java's `collectingAndThen()` additionally clears `IDENTITY_FINISH` from what it
derives, since adding a finisher is precisely what makes the finish
non-identity. That clearing is not specified here because `IDENTITY_FINISH` is
not defined; if it is ever added, the clearing SHALL be added with it.

#### Scenario: Adapting an unordered downstream stays unordered
- **WHEN** the collector returned by `collecting_and_then(to_set(), frozenset)`
  is asked for its characteristics
- **THEN** `UNORDERED` is present

#### Scenario: Adapting an ordered downstream stays ordered
- **WHEN** the collector returned by `collecting_and_then(to_list(), tuple)` is
  asked for its characteristics
- **THEN** `UNORDERED` is absent

#### Scenario: Composing the two adapters derives through both
- **WHEN** the collector returned by
  `collecting_and_then(mapping(len, to_set()), frozenset)` is asked for its
  characteristics
- **THEN** `UNORDERED` is present

### Requirement: `collecting_and_then()` derives its combiner from its downstream

`collecting_and_then()`'s collector SHALL declare a `combiner` only where its
downstream declares one, merging the downstream's container directly via the
downstream's own combiner - `finisher` runs once, in `_finish`, on the
container that survived every merge, never once per partition. Where the
downstream declares no combiner, `collecting_and_then()`'s collector SHALL
declare none either.

#### Scenario: Parallel result over several batches matches sequential, combinable downstream
- **WHEN** a source spanning more than one batch is collected with `collecting_and_then(to_list(), sorted)` under `.parallel()`
- **THEN** the result equals the sequential result

#### Scenario: A non-combinable downstream declares no combiner
- **WHEN** `collecting_and_then(summing_double(mapper), finisher).combiner` is read
- **THEN** it is `None`
