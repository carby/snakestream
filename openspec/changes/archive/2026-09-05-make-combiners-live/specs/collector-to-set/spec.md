## ADDED Requirements

### Requirement: `to_set()` declares a combiner

`to_set()`'s collector SHALL declare a `combiner` that merges two partial
sets by union (`set.update`). Set union is associative independently of the
collector's `UNORDERED` declaration — the two are independent properties
(`parallel-reduction`).

#### Scenario: Parallel result over several batches matches sequential
- **WHEN** a source spanning more than one batch is collected with `to_set()` under `.parallel()`
- **THEN** the result equals the sequential result, and the combiner was invoked at least once
