## ADDED Requirements

### Requirement: Property-based test coverage for core stream operations
The test suite SHALL include `hypothesis`-driven property tests for `Stream.map`, `Stream.filter`, `Stream.reduce`, `Stream.sorted`, and `Stream.distinct`, each asserting the operation's general invariant against a plain-Python reference computation over generated inputs, in addition to the existing example-based tests for those operations.

#### Scenario: map output matches reference for generated inputs
- **WHEN** a `hypothesis`-generated list of values is passed through `Stream.of(values).map(mapper).collect(to_list)` for a given `mapper`
- **THEN** the result equals `list(map(mapper, values))`

#### Scenario: filter output matches reference for generated inputs
- **WHEN** a `hypothesis`-generated list of values is passed through `Stream.of(values).filter(predicate).collect(to_list)` for a given `predicate`
- **THEN** the result equals `list(filter(predicate, values))`

#### Scenario: reduce output matches reference for generated inputs
- **WHEN** a `hypothesis`-generated list of values and an identity are passed through `Stream.of(values).reduce(identity, accumulator)`
- **THEN** the result equals `functools.reduce(accumulator, values, identity)`

#### Scenario: sorted output matches reference for generated inputs
- **WHEN** a `hypothesis`-generated list of values is passed through `Stream.of(values).sorted().collect(to_list)` (default ordering) or with an explicit 3-way `Comparator`
- **THEN** the result is a permutation of `values`, is non-decreasing per the ordering used, and preserves the relative order of equal elements (stability), matching Python's `sorted()` behavior for the same key/comparator

#### Scenario: distinct output matches reference for generated inputs
- **WHEN** a `hypothesis`-generated list of hashable values is passed through `Stream.of(values).distinct().collect(to_list)`
- **THEN** the result contains each distinct value from `values` exactly once, in first-seen order

#### Scenario: empty and single-element streams are handled
- **WHEN** any of `map`, `filter`, `reduce`, `sorted`, `distinct` is run on an empty input or a single-element input via `hypothesis`
- **THEN** the operation completes without error and its output matches the plain-Python reference for that same edge-case input

#### Scenario: async user-supplied callables are covered
- **WHEN** an `async def` mapper, predicate, accumulator, or comparator is supplied to `map`, `filter`, `reduce`, or `sorted` respectively, on a `hypothesis`-generated input
- **THEN** the result matches the same reference computation as the synchronous-callable case
