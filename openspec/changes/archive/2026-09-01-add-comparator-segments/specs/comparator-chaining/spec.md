## MODIFIED Requirements

### Requirement: A key-based comparator composes with a tie-break ordering
The value `comparing()` returns SHALL expose a `then_comparing(other)` operation
that produces a comparator ordering by the original ordering first and by
`other` only where the original treats two elements as equivalent. `other` MAY
be a key extractor, in which case it contributes one ascending ordering; another
key-based comparator, in which case its whole ordering — every component and
every direction — is appended; or a `Comparator`, in which case it contributes
that ordering directly. `then_comparing()` SHALL additionally accept an optional
second positional argument, a `key_comparator`, ordering the keys the first
argument extracts. The requirements for a supplied `Comparator` in either
position, and for telling one from a key extractor, are stated in
`comparator-key-comparator`. Composition SHALL be repeatable to any depth, and
the resulting comparator SHALL itself be accepted anywhere a `Comparator` is
accepted.

#### Scenario: the second ordering breaks ties in the first
- **WHEN** records `[("b", 1), ("a", 2), ("a", 1)]` are sorted by a comparator ordering on the first field and then on the second
- **THEN** the result is `[("a", 1), ("a", 2), ("b", 1)]`

#### Scenario: the first ordering wins where it is decisive
- **WHEN** records are sorted by a chained comparator and no two elements share a first key
- **THEN** the order is exactly the order the first ordering alone produces, and the result does not depend on the second key

#### Scenario: chaining accepts another key-based comparator
- **WHEN** a key-based comparator is passed to `then_comparing()` instead of a bare key extractor
- **THEN** the resulting order is identical to passing that comparator's key extractor directly, and the passed comparator's own direction is preserved

#### Scenario: chains of three or more orderings
- **WHEN** three orderings are chained and the first two are equivalent for a pair of elements
- **THEN** the third ordering decides that pair

#### Scenario: a chained comparator is usable by every comparator-consuming operation
- **WHEN** a chained comparator is passed to `sorted()`, `min()`, `max()`, `min_by()` or `max_by()`
- **THEN** each operates on the chained ordering with no signature change

#### Scenario: a one-argument call keeps its existing meaning
- **WHEN** `then_comparing()` is called with a single key extractor
- **THEN** it contributes one ascending key-based ordering, exactly as before a `Comparator` was accepted

### Requirement: Every segment of a chain may be sync or async
Each key extractor in a chained comparator SHALL be independently either sync or
async, and a chain SHALL support any mixture of the two. An async extractor's
key SHALL be awaited and its awaited value used. The resulting order SHALL be
identical to the order produced by equivalent sync extractors. A `Comparator`
supplied as an ordering is the one exception and MUST be sync, per
`comparator-key-comparator`; this constrains the comparator only, never an
extractor accompanying it.

#### Scenario: a chain of async extractors orders correctly
- **WHEN** a chain whose extractors are all `async def` is used to sort
- **THEN** the order matches that of the equivalent all-sync chain

#### Scenario: a chain mixing sync and async extractors orders correctly
- **WHEN** a chain whose first extractor is sync and whose second is `async def` is used to sort
- **THEN** the order matches that of the equivalent all-sync chain

#### Scenario: an async chain works with min() and max()
- **WHEN** a chained comparator with async extractors is passed to `min()` or `max()`
- **THEN** the extractors are awaited and the correct extreme element is returned

#### Scenario: an async extractor may accompany a sync supplied comparator
- **WHEN** a chain contains a segment built from an `async def` extractor and a sync key comparator
- **THEN** the extractor is awaited and the keys are ordered by the supplied comparator
