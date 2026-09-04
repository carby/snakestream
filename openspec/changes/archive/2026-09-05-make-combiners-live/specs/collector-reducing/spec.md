## ADDED Requirements

### Requirement: All three `reducing()` forms declare a combiner

`reducing()`'s collector — for all three overloads (no identity, identity
only, identity plus mapper) — SHALL declare a `combiner` that folds two
partial accumulations using the same `binary_operator` the accumulator uses.
For the no-identity form, an empty partition's accumulation carries no value
and contributes nothing to the merge — the same rule the accumulator applies
to an empty stream, applied once more across partitions.

#### Scenario: Parallel result over several batches matches sequential, no identity
- **WHEN** a source spanning more than one batch is collected with `reducing(binary_operator)` under `.parallel()`
- **THEN** the result equals the sequential result

#### Scenario: Parallel result over several batches matches sequential, with identity
- **WHEN** a source spanning more than one batch is collected with `reducing(identity, binary_operator)` under `.parallel()`
- **THEN** the result equals the sequential result

#### Scenario: An empty partition contributes nothing to the no-identity merge
- **WHEN** a filter thins some batches to zero elements before `reducing(binary_operator)` collects the rest under `.parallel()`
- **THEN** the result equals the sequential result over the same filtered source
