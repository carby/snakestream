## ADDED Requirements

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
