## ADDED Requirements

### Requirement: `mapping()` derives its combiner from its downstream

`mapping()`'s collector SHALL declare a `combiner` only where its downstream
declares one, merging by calling the downstream's own combiner on the two
mapped containers directly - the mapper runs per element and the result is
the downstream's unchanged, so combinability, like `Characteristics`, carries
over from the downstream as-is. Where the downstream declares no combiner,
`mapping()`'s collector SHALL declare none either.

#### Scenario: Parallel result over several batches matches sequential, combinable downstream
- **WHEN** a source spanning more than one batch is collected with `mapping(mapper, to_list())` under `.parallel()`
- **THEN** the result equals the sequential result

#### Scenario: A non-combinable downstream declares no combiner
- **WHEN** `mapping(mapper, summing_double(inner_mapper)).combiner` is read
- **THEN** it is `None`
