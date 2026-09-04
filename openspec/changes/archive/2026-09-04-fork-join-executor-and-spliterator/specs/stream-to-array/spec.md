## MODIFIED Requirements

### Requirement: `Stream.to_array()` terminal operation
`Stream.to_array()` SHALL be a terminal operation, callable with no arguments, that drives the stream's chain under its executor and returns a `list` containing every element pulled from the composed chain, in the same order `collect(to_list())` would return them. It SHALL be equivalent in behavior to `self.collect(to_list())` and SHALL be available under either executor with no mode-specific override, following the existing precedent of terminal ops like `iterator()`. It is named `to_array` (snake_case), matching every other Java-name adaptation already in the class (`for_each`, `find_any`, `flat_map`), rather than the literal Java casing `toArray`.

#### Scenario: Returns a list of all elements, sequential
- **WHEN** `Stream.of([1, 2, 3]).to_array()` is called
- **THEN** the result is `[1, 2, 3]`

#### Scenario: Empty stream returns an empty list
- **WHEN** `to_array()` is called on a stream with no elements
- **THEN** the result is `[]`

#### Scenario: Equivalent to `collect(to_list)`
- **WHEN** the same chain is terminated once with `to_array()` and once with `collect(to_list())`
- **THEN** both calls return equal lists

#### Scenario: Works under RACING execution
- **WHEN** `to_array()` is called on a stream using the fork-join executor
- **THEN** the result is a `list` containing all source elements (order not guaranteed, matching the fork-join executor's existing unordered semantics)
