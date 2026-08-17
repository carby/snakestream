## ADDED Requirements

### Requirement: `Stream.to_array()` terminal operation
`Stream.to_array()` SHALL be a terminal operation, callable with no arguments, that drives `self._compose()` and returns a `list` containing every element pulled from the composed chain, in the same order `collect(to_list)` would return them. It SHALL be equivalent in behavior to `self.collect(to_list)` and SHALL be available on both `Stream` (sequential) and `ParallelStream` (parallel) instances with no subclass-specific override, following the existing precedent of terminal ops like `iterator()`. It is named `to_array` (snake_case), matching every other Java-name adaptation already in the class (`for_each`, `find_any`, `flat_map`), rather than the literal Java casing `toArray`.

#### Scenario: Returns a list of all elements, sequential
- **WHEN** `Stream.of([1, 2, 3]).to_array()` is called
- **THEN** the result is `[1, 2, 3]`

#### Scenario: Empty stream returns an empty list
- **WHEN** `to_array()` is called on a stream with no elements
- **THEN** the result is `[]`

#### Scenario: Equivalent to `collect(to_list)`
- **WHEN** the same chain is terminated once with `to_array()` and once with `collect(to_list)`
- **THEN** both calls return equal lists

#### Scenario: Works on `ParallelStream`
- **WHEN** `to_array()` is called on a `ParallelStream` instance
- **THEN** the result is a `list` containing all source elements (order not guaranteed, matching `ParallelStream`'s existing unordered semantics)

### Requirement: No `toArray(generator)` overload
`Stream.to_array()` SHALL NOT accept a factory/generator argument. Java's `toArray(IntFunction<A[]> generator)` overload exists to produce a correctly-typed array in a language without runtime generic-array construction; Python's `list` has no equivalent typed-container problem, so this overload SHALL be treated as intentionally skipped rather than implemented.

#### Scenario: Calling with an argument raises
- **WHEN** `to_array()` is called with any positional or keyword argument
- **THEN** a `TypeError` is raised (Python's standard no-such-parameter behavior, not custom validation)
