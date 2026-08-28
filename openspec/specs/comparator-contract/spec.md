## Purpose

Defines the single 3-way `Comparator` contract shared by `sorted()`, `min()`, and `max()` on `Stream` — a comparison function returning an int whose sign indicates ordering (negative/zero/positive), matching Java's `Comparator<T>` — plus what all three do with elements that compare equal: `min()` and `max()` keep the earlier-encountered one, and `sorted()` is stable, which is the same rule read over a whole stream rather than one running result. On an ordered pipeline that holds under `parallel()` as well as sequentially; on a pipeline declared `unordered()` the `min()`/`max()` tie is explicitly unspecified. One capability owns the tie question for every comparator-consuming operation, so they behave consistently and predictably.

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
When two elements compare as equal (`comparator(a, b) == 0`), `min()` and
`max()` SHALL both retain the earlier-encountered element as the running
result, not the later one, on any pipeline that carries an encounter-order
requirement at the end of its chain — under the sequential executor and under
`parallel()` alike. On such a pipeline the element returned SHALL be the same
one the sequential pipeline returns.

Where the pipeline carries no encounter-order requirement at the end of its
chain — a pipeline declared `unordered()` — which of two tied elements is
returned is unspecified, and `min()`/`max()` SHALL take the order-blind path
and pay nothing for this requirement. This matches Java, whose parallel
`min()`/`max()` on an unordered pipeline may break ties any way. A caller who
wants a determinate answer without an ordering barrier SHALL supply a total
comparator, for which `then_comparing()` is the lever.

The value returned is unaffected either way whenever the comparator is
consistent with equality; only which of two equal-comparing but distinguishable
elements is returned depends on the pipeline's ordering.

#### Scenario: max() keeps the first of equal maximums
- **WHEN** `Stream.of([("a", 5), ("b", 5)]).max(lambda x, y: x[1] - y[1])` is awaited
- **THEN** the result is `("a", 5)`

#### Scenario: min() keeps the first of equal minimums
- **WHEN** `Stream.of([("a", 5), ("b", 5)]).min(lambda x, y: x[1] - y[1])` is awaited
- **THEN** the result is `("a", 5)`

#### Scenario: An ordered racing max() keeps the first of equal maximums
- **WHEN** a stream over distinguishable records whose comparator keys tie is
  run under `.parallel()` with a mapping operation of variable per-element cost
  and `max()` is awaited
- **THEN** the result is the tied record earliest in encounter order, equal to
  the sequential pipeline's result, and is the same on every run

#### Scenario: An ordered racing min() keeps the first of equal minimums
- **WHEN** the same pipeline is run with `min()`
- **THEN** the result is the tied record earliest in encounter order, equal to
  the sequential pipeline's result

#### Scenario: An unordered racing max() may return either tied element
- **WHEN** `.parallel().unordered()` precedes `max()` over tied records
- **THEN** the result is one of the tied records, no delivery barrier is
  engaged, and no error is raised

#### Scenario: A total comparator is determinate on an unordered pipeline
- **WHEN** `.parallel().unordered().max(comparing(key).then_comparing(tiebreak))`
  is awaited over records whose first key ties
- **THEN** the result is the record the tie-break segment selects, and is the
  same on every run

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
### Requirement: sorted() is stable
`sorted()` SHALL be stable: elements that compare as equal
(`comparator(a, b) == 0`) SHALL appear in the sorted output in the same
relative order they held on entry to the sort. This SHALL hold for every
comparator form the capability accepts — a sync comparator, an async
comparator, and a `comparing()` key comparator with any number of segments in
any direction.

Stability SHALL hold under `parallel()` as well as sequentially, and SHALL hold
on a pipeline declared `unordered()`: a sort claims its output is ordered, so
it sees the whole stream in encounter order regardless of the ordering
characteristic at its own position, and the relative order it preserves is
therefore encounter order.

This is the same rule as `min()`/`max()`'s tie-break, read over a whole stream
rather than a single running result, which is why one capability states both.

#### Scenario: A sync comparator sort preserves the order of tied elements
- **WHEN** `Stream.of([("a", 5), ("b", 3), ("c", 5)]).sorted(lambda x, y: x[1] - y[1])`
  is collected
- **THEN** the result is `[("b", 3), ("a", 5), ("c", 5)]`

#### Scenario: An async comparator sort preserves the order of tied elements
- **WHEN** the same source is sorted with an `async def` comparator over the
  same key
- **THEN** the result is the same, with `("a", 5)` before `("c", 5)`

#### Scenario: A key comparator sort preserves the order of tied elements
- **WHEN** the same source is sorted with `comparing(lambda x: x[1])`
- **THEN** the result is the same, with `("a", 5)` before `("c", 5)`

#### Scenario: A reversed key comparator is stable rather than reversing ties
- **WHEN** the same source is sorted with `comparing(lambda x: x[1]).reversed()`
- **THEN** the result is `[("a", 5), ("c", 5), ("b", 3)]` — the tied pair keeps
  its encounter order rather than being reversed with the ordering

#### Scenario: A racing sort is stable
- **WHEN** the same sort runs under `.parallel()` behind a mapping operation of
  variable per-element cost
- **THEN** the result equals the sequential result exactly, tied elements
  included, on every run

#### Scenario: A sort on an unordered pipeline is stable
- **WHEN** `.parallel().unordered()` precedes the same sort
- **THEN** the sort still sees the whole stream and the result equals the
  sequential result exactly, tied elements included
