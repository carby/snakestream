## MODIFIED Requirements

### Requirement: Comparators must not return bool
`sorted()`, `min()`, and `max()` on `Stream` SHALL raise `TypeError` if a user-supplied `Comparator` returns a value of type `bool`, whether the comparator is sync or `async`. This guards the 3-way `int` contract (defined in "Single 3-way Comparator contract") against Python's `bool <: int` subtyping, which would otherwise let a boolean predicate (e.g. `lambda x, y: x > y`) satisfy the `Comparator` type statically while silently violating its sign semantics (a bool result can never be negative, so "orders before" can never be signaled).

The exception raised SHALL be `ComparatorContractException` from `snakestream.exception`, which derives from `TypeError` (see `exception-hierarchy`). `TypeError` remains the guarantee callers may rely on and the type this requirement is stated in terms of; the subclass adds catchability under the library's own hierarchy without narrowing it. A caller SHALL NOT need to name the subclass: `except TypeError` catches every rejection this requirement mandates.

The same rejection SHALL apply to any non-`int` return, not only `bool`; `bool` is called out because it is the one that type-checks as an `int` and therefore fails silently without this guard.

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

#### Scenario: the rejection is catchable as a library exception
- **WHEN** `Stream.of([3, 1, 2]).sorted(lambda a, b: a > b)` is collected inside a `try` catching only `StreamException`
- **THEN** the rejection is caught, and the same exception also satisfies `except TypeError`

#### Scenario: a non-int, non-bool return is rejected the same way
- **WHEN** a comparator returning `str` is passed to `sorted()`
- **THEN** a `TypeError` is raised naming the returned type
