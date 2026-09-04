## ADDED Requirements

### Requirement: `grouping_by()` derives its combiner from its downstream

`grouping_by()`'s collector SHALL declare a `combiner` only where its
downstream collector declares one - the same rule this factory already uses
to derive `Characteristics` from its downstream, applied once more. That
combiner SHALL merge two partial group maps by key: a key present in only
one side is copied across; a key present in both is merged by calling the
downstream's own combiner on the two group containers. Where the downstream
declares no combiner, `grouping_by()`'s collector SHALL declare none either,
and the collection SHALL fall back to today's single-container behavior
rather than a wrong answer.

This derivation does not depend on whether a `map_factory` was supplied
(unlike the `UNORDERED` derivation, which is bounded to the default `dict`
container): merging two partial mappings by key works the same way over any
`MutableMapping`.

#### Scenario: Parallel result over several batches matches sequential, combinable downstream
- **WHEN** a source spanning more than one batch is collected with `grouping_by(classifier, counting())` under `.parallel()`
- **THEN** the result equals the sequential result

#### Scenario: A non-combinable downstream declares no combiner
- **WHEN** `grouping_by(classifier, summing_double(mapper)).combiner` is read
- **THEN** it is `None`, and the collection is not partitioned, but the result under `.parallel()` still equals the sequential result
