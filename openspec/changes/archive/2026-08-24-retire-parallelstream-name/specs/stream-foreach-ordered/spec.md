## MODIFIED Requirements

### Requirement: for_each_ordered() preserves encounter order under RACING execution
`Stream.for_each_ordered(consumer)`, when called on a stream whose executor is `RACING` (i.e. `.parallel()` was the last mode switch before this call), SHALL invoke `consumer` in the stream's encounter order, even though `RACING`'s branch-racing execution does not itself preserve order and `for_each()` on the same stream makes no such guarantee.

#### Scenario: A RACING stream yields ordered results via for_each_ordered
- **WHEN** a stream built from an ordered source and switched to `RACING` execution (e.g. `Stream.of([1, 2, 3, 4]).parallel()`) has `.for_each_ordered(consumer)` called on it
- **THEN** `consumer` is invoked with `1`, then `2`, then `3`, then `4`, in that order — the same order `for_each_ordered()` would produce on the equivalent `SEQUENTIAL` stream

#### Scenario: for_each_ordered does not alter for_each's behavior
- **WHEN** `for_each()` is called on a stream using `RACING` execution (unrelated to any `for_each_ordered()` call)
- **THEN** `for_each()`'s existing unordered-completion behavior is unchanged
