## ADDED Requirements

### Requirement: Comparators must not return bool
`sorted()`, `min()`, and `max()` on `Stream` SHALL raise `TypeError` if a user-supplied `Comparator` returns a value of type `bool`, whether the comparator is sync or `async`. This guards the 3-way `int` contract (defined in "Single 3-way Comparator contract") against Python's `bool <: int` subtyping, which would otherwise let a boolean predicate (e.g. `lambda x, y: x > y`) satisfy the `Comparator` type statically while silently violating its sign semantics (a bool result can never be negative, so "orders before" can never be signaled).

#### Scenario: sorted() rejects a bool comparator
- **WHEN** `Stream.of([3, 1, 2]).sorted(lambda a, b: a > b)` is collected
- **THEN** a `TypeError` is raised before any ordering result is returned

#### Scenario: max() rejects a bool comparator
- **WHEN** `Stream.of([3, 1, 2]).max(lambda a, b: a > b)` is awaited
- **THEN** a `TypeError` is raised

#### Scenario: min() rejects a bool comparator
- **WHEN** `Stream.of([3, 1, 2]).min(lambda a, b: a > b)` is awaited
- **THEN** a `TypeError` is raised

#### Scenario: async bool comparator is rejected identically
- **WHEN** an `async def` comparator returning `bool` is passed to `sorted()`, `min()`, or `max()`
- **THEN** a `TypeError` is raised after the comparator is awaited, using the same rejection as the sync case

#### Scenario: a proper 3-way int comparator is unaffected
- **WHEN** `Stream.of([3, 1, 2]).max(lambda a, b: a - b)` is awaited
- **THEN** no error is raised and the result is `3`
