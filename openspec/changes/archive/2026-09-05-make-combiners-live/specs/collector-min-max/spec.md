## ADDED Requirements

### Requirement: `min_by()`/`max_by()` declare a combiner that preserves first-of-tied-wins

`min_by(comparator)`'s and `max_by(comparator)`'s collectors SHALL each
declare a `combiner` that merges two partial extrema left-biased: the first
partition's (in batch order) held element wins on a tie, exactly as the
per-element accumulator keeps the earlier-seen element on a tie. This holds
even though `min_by`/`max_by` decline `Characteristics.UNORDERED` — declaring
a combiner is independent of declaring `UNORDERED` (`parallel-reduction`), and
this pair is the case that proves it: the tie-break must still follow
encounter order, and a left-biased merge over contiguous partitions preserves
exactly that.

#### Scenario: Parallel result over several batches matches sequential
- **WHEN** a source spanning more than one batch is collected with `min_by(comparator)` under `.parallel()`
- **THEN** the result equals the sequential result

#### Scenario: A tie is broken by encounter order across partitions
- **WHEN** every element of a multi-batch source compares equal under `comparator`, and is collected with `min_by(comparator)` under `.parallel()`
- **THEN** the result is the first element in encounter order, matching the sequential result
