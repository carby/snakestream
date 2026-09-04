## ADDED Requirements

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
