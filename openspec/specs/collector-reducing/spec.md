## Purpose

Fold/reduction collectors for use with `Stream.collect()`, mirroring Java's
three `Collectors.reducing(...)` overloads.

## Requirements

### Requirement: `reducing(binary_operator)` collector factory (no identity)
`collector.py` SHALL provide a `reducing(binary_operator)` form — the
single-arg overload — returning a collector that folds the stream's elements
pairwise via `binary_operator` (sync or async), using the first pulled
element to seed the fold, and returns `T | None`, matching Java's
`Collectors.reducing(BinaryOperator<T>)` (`Optional<T>` in Java, `None` for
an empty stream in this project's `T | None` convention). Mirrors
`Stream.reduce(accumulator)`'s existing semantics exactly.

#### Scenario: folds elements with the first as seed
- **WHEN** `Stream.of([1, 2, 3, 4]).collect(reducing(lambda a, b: a + b))` is called
- **THEN** the result is `10`

#### Scenario: empty stream yields None
- **WHEN** `Stream.of([]).collect(reducing(lambda a, b: a + b))` is called
- **THEN** the result is `None`

#### Scenario: single-element stream returns that element without calling the operator
- **WHEN** `Stream.of([5]).collect(reducing(lambda a, b: a + b))` is called
- **THEN** the result is `5`

### Requirement: `reducing(identity, binary_operator)` collector factory
`collector.py` SHALL provide the 2-arg `reducing(identity, binary_operator)`
overload, returning a collector that folds the stream's elements starting
from `identity` and returns `T` (never `None`, even for an empty stream —
`identity` is returned unchanged), matching Java's
`Collectors.reducing(T identity, BinaryOperator<T> op)`. Mirrors
`Stream.reduce(identity, accumulator)`'s existing semantics exactly.

#### Scenario: folds elements starting from identity
- **WHEN** `Stream.of([1, 2, 3]).collect(reducing(10, lambda a, b: a + b))` is called
- **THEN** the result is `16`

#### Scenario: empty stream returns identity unchanged
- **WHEN** `Stream.of([]).collect(reducing(10, lambda a, b: a + b))` is called
- **THEN** the result is `10`

### Requirement: `reducing(identity, mapper, binary_operator)` collector factory
`collector.py` SHALL provide the 3-arg `reducing(identity, mapper,
binary_operator)` overload, returning a collector that maps every pulled
element via `mapper` (sync or async) and folds the mapped values starting
from `identity` via `binary_operator` (sync or async), returning `U`,
matching Java's `Collectors.reducing(U identity, Function<T,U> mapper,
BinaryOperator<U> op)` — argument order is identity, then mapper, then fold
operator, matching Java exactly.

#### Scenario: maps then folds starting from identity
- **WHEN** `Stream.of(["a", "bb", "ccc"]).collect(reducing(0, len, lambda a, b: a + b))` is called
- **THEN** the result is `6`

#### Scenario: empty stream returns identity unchanged
- **WHEN** `Stream.of([]).collect(reducing(0, len, lambda a, b: a + b))` is called
- **THEN** the result is `0`

#### Scenario: async mapper and async binary_operator are both awaited
- **WHEN** `reducing(identity, mapper, binary_operator)` is given an async mapper and/or an async binary_operator
- **THEN** the result is computed correctly, with each awaited via the same dispatch used elsewhere in the library

### Requirement: overload dispatch matches Java's arg count exactly
`collector.py`'s `reducing` SHALL dispatch between the three overloads
strictly by positional argument count (1, 2, or 3 args), with no keyword-only
disambiguation required, matching how Java's overload resolution picks
between the three `reducing` signatures.

#### Scenario: one positional arg selects the no-identity form
- **WHEN** `reducing(op)` is called with a single positional argument
- **THEN** it is treated as `binary_operator` with no identity, per the no-identity overload

#### Scenario: two positional args select the identity form
- **WHEN** `reducing(identity, op)` is called with two positional arguments
- **THEN** it is treated as `(identity, binary_operator)`, per the identity overload

#### Scenario: three positional args select the mapper form
- **WHEN** `reducing(identity, mapper, op)` is called with three positional arguments
- **THEN** it is treated as `(identity, mapper, binary_operator)`, per the mapper overload

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
