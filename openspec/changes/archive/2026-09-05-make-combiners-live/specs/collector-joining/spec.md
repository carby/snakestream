## ADDED Requirements

### Requirement: `joining()` declares a combiner

`joining()`'s collector SHALL declare a `combiner` that concatenates two
partial part-lists (the same list-of-parts accumulation `to_list()` uses),
merged before `delimiter`/`prefix`/`suffix` are ever applied — the finisher
runs once, on the fully-merged list.

#### Scenario: Parallel result over several batches matches sequential
- **WHEN** a source spanning more than one batch is collected with `joining(delimiter=",")` under `.parallel()`
- **THEN** the result equals the sequential result
