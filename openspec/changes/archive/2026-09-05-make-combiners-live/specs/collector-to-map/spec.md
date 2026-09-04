## ADDED Requirements

### Requirement: The two-argument `to_map` form declares a combiner

`to_map(key_mapper, value_mapper)` (no `merge_function`) SHALL declare a
`combiner` that merges two partial maps by key, applying the same
"duplicate key raises `IllegalStateException`" rule the accumulator applies
- once more, across two partitions instead of within one. Which colliding
key the exception names is not guaranteed under `.parallel()` once two or
more distinct collisions are in play (`collector-to-map`'s existing
"duplicate-key exception names a colliding key, not a particular one"
requirement already covers this).

#### Scenario: Parallel result over several batches matches sequential
- **WHEN** a source spanning more than one batch, with no colliding keys, is collected with `to_map(key_mapper, value_mapper)` under `.parallel()`
- **THEN** the result equals the sequential result

#### Scenario: A duplicate key across two different partitions still raises
- **WHEN** two elements landing in two different batches map to the same key, collected with `to_map(key_mapper, value_mapper)` under `.parallel()`
- **THEN** `IllegalStateException` is raised

### Requirement: The three-argument `to_map` form declares no combiner

`to_map(key_mapper, value_mapper, merge_function)` SHALL declare no
`combiner`. `merge_function` is caller-supplied and not required to be
associative, so lifting it into a combiner would silently impose a contract
the caller never agreed to. This holds regardless of the four-argument form's
`map_supplier`, which never reaches this decision - the three- and
four-argument forms both always carry a `merge_function`.

#### Scenario: The three-argument form declares no combiner
- **WHEN** `to_map(key_mapper, value_mapper, merge_function).combiner` is read
- **THEN** it is `None`, and a `.parallel()` collection with it is not partitioned
