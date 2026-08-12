## Purpose

Defines the single 3-way `Comparator` contract shared by `sorted()`, `min()`, and `max()` on `Stream` — a comparison function returning an int whose sign indicates ordering (negative/zero/positive), matching Java's `Comparator<T>` — plus `min()`'s and `max()`'s shared tie-break behavior of keeping the earlier-encountered element, so all comparator-consuming operations behave consistently and predictably.

## Requirements

### Requirement: Single 3-way Comparator contract
The `Comparator` type SHALL represent a 3-way comparison function returning a negative int when the first argument orders before the second, zero when they are equivalent, and a positive int when the first argument orders after the second (sync or `Awaitable[int]`). `sorted()`, `min()`, and `max()` on `Stream` SHALL all interpret a user-supplied `Comparator` argument using this same contract — no operation SHALL treat it as a boolean predicate.

#### Scenario: sorted() orders ascending by comparator sign
- **WHEN** `Stream.of([3, 1, 2]).sorted(lambda a, b: a - b)` is collected
- **THEN** the result is `[1, 2, 3]`

#### Scenario: max() selects the greatest element by comparator sign
- **WHEN** `Stream.of([3, 1, 2]).max(lambda a, b: a - b)` is awaited
- **THEN** the result is `3`

#### Scenario: min() selects the least element by comparator sign
- **WHEN** `Stream.of([3, 1, 2]).min(lambda a, b: a - b)` is awaited
- **THEN** the result is `1`

#### Scenario: async comparator is supported identically
- **WHEN** an `async def` 3-way comparator is passed to `sorted()`, `min()`, or `max()`
- **THEN** it is awaited and its return value interpreted by the same sign contract as the sync case

### Requirement: min() and max() keep the first of tied elements
When two elements compare as equal (`comparator(a, b) == 0`), `min()` and `max()` SHALL both retain the earlier-encountered element as the running result, not the later one.

#### Scenario: max() keeps the first of equal maximums
- **WHEN** `Stream.of([("a", 5), ("b", 5)]).max(lambda x, y: x[1] - y[1])` is awaited
- **THEN** the result is `("a", 5)`

#### Scenario: min() keeps the first of equal minimums
- **WHEN** `Stream.of([("a", 5), ("b", 5)]).min(lambda x, y: x[1] - y[1])` is awaited
- **THEN** the result is `("a", 5)`

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
