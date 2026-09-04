## ADDED Requirements

### Requirement: `partitioning_by()` derives its combiner from its downstream

`partitioning_by()`'s collector SHALL declare a `combiner` only where its
downstream collector declares one, merging the `True` and `False` buckets of
two partial results by calling the downstream's own combiner on each bucket
pair - both buckets always exist (seeded in the supplier), so there is no
present-in-only-one-side case here, unlike `grouping_by()`'s arbitrary key
set. Where the downstream declares no combiner, `partitioning_by()`'s
collector SHALL declare none either.

#### Scenario: Parallel result over several batches matches sequential, combinable downstream
- **WHEN** a source spanning more than one batch is collected with `partitioning_by(predicate, counting())` under `.parallel()`
- **THEN** the result equals the sequential result

#### Scenario: A non-combinable downstream declares no combiner
- **WHEN** `partitioning_by(predicate, summing_double(mapper)).combiner` is read
- **THEN** it is `None`
