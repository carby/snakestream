## Purpose

Defines how an ordering may be supplied as a `Comparator` wherever the library
would otherwise apply natural ordering to a key — as a bare tie-break, or as
the ordering used on an extracted key — matching Java's `thenComparing(Comparator)`
and the two-argument `comparing`/`thenComparing` overloads. It also defines how
such a callable is told apart from a key extractor, and which comparators are
refused, so that a supplied ordering composes with direction, null tolerance
and stability exactly as a key-based one does.

## ADDED Requirements

### Requirement: A bare Comparator is accepted as a tie-break ordering
`then_comparing(other)` SHALL accept a two-argument `Comparator` as `other`,
contributing an ordering that is consulted only where the orderings before it
treat two elements as equivalent. The resulting comparator SHALL be accepted
anywhere a `Comparator` is accepted, and SHALL remain composable — a further
`then_comparing()` or a `reversed()` applied to it SHALL behave as it does for
any other chain.

#### Scenario: a supplied comparator breaks ties
- **WHEN** records `[("b", 1), ("a", 2), ("a", 1)]` are sorted by an ordering on the first field, chained with a bare comparator comparing the second field
- **THEN** the result is `[("a", 1), ("a", 2), ("b", 1)]`

#### Scenario: the earlier ordering still wins where it is decisive
- **WHEN** no two elements share a first key
- **THEN** the supplied comparator does not affect the order

#### Scenario: a supplied comparator is consulted by every comparator-consuming operation
- **WHEN** a chain ending in a supplied comparator is passed to `sorted()`, `min()`, `max()`, `min_by()` or `max_by()`
- **THEN** each operates on that ordering with no signature change

#### Scenario: a supplied comparator can be chained onto further
- **WHEN** a third ordering is chained after a supplied comparator and the first two are equivalent for a pair
- **THEN** the third ordering decides that pair

### Requirement: An ordering may be supplied for an extracted key
`comparing(key_extractor, key_comparator)` and
`then_comparing(key_extractor, key_comparator)` SHALL order elements by
applying `key_comparator` to the keys `key_extractor` produces, rather than by
the keys' natural ordering. Both SHALL be equivalent in result to supplying a
bare comparator that extracts both keys itself and compares them.

#### Scenario: keys are ordered by the supplied comparator, not naturally
- **WHEN** elements are sorted by `comparing(key_extractor, key_comparator)` where `key_comparator` reverses natural key order
- **THEN** the result is the reverse of the order `comparing(key_extractor)` alone produces

#### Scenario: the two-argument tie-break form orders identically
- **WHEN** `then_comparing(key_extractor, key_comparator)` is chained onto an ordering
- **THEN** ties in the earlier ordering are broken exactly as by a bare comparator that extracts both keys and applies `key_comparator` to them

#### Scenario: keys with no natural ordering are still orderable
- **WHEN** the extracted keys do not support `<` among themselves but the supplied comparator orders them
- **THEN** the sort succeeds and follows the supplied comparator

### Requirement: A supplied ordering must be synchronous
Where a `Comparator` is supplied as an ordering — bare, or applied to an
extracted key — it MUST be synchronous. An async comparator SHALL be rejected
at the point the comparator is built, not when a sort or comparison runs, and
the error SHALL name the supported alternatives. A key extractor accompanying
a supplied comparator MAY still be async.

#### Scenario: an async bare comparator is rejected at construction
- **WHEN** an `async def` comparator is passed to `then_comparing()`
- **THEN** the call raises immediately, before any element is seen

#### Scenario: an async key comparator is rejected at construction
- **WHEN** an `async def` comparator is passed as the second argument to `comparing()` or `then_comparing()`
- **THEN** the call raises immediately, before any element is seen

#### Scenario: the error explains what is supported instead
- **WHEN** an async comparator is rejected
- **THEN** the error message names both an async key extractor segment and a bare async comparator passed directly to `sorted()` as the supported alternatives

#### Scenario: an async key extractor with a sync key comparator is accepted
- **WHEN** `comparing(async_key_extractor, sync_key_comparator)` is used to sort
- **THEN** the extractor is awaited for each element and the resulting keys are ordered by the supplied comparator

### Requirement: A supplied comparator is told from a key extractor by its arity
Where a single callable may be either a key extractor or a `Comparator`, it
SHALL be classified by the number of positional parameters it accepts: one
means a key extractor, two means a `Comparator`. A callable whose arity cannot
be determined SHALL be treated as a key extractor, which is the meaning such a
callable already carries. A callable that is itself a key-based comparator
SHALL continue to be recognised as such and take precedence over arity.

#### Scenario: a one-argument callable is a key extractor
- **WHEN** a one-argument callable is passed to `then_comparing()`
- **THEN** it contributes one ascending key-based ordering, as it does today

#### Scenario: a two-argument callable is a comparator
- **WHEN** a two-argument callable is passed to `then_comparing()`
- **THEN** it contributes a supplied ordering rather than being called with one argument

#### Scenario: a key-based comparator is spliced rather than classified by arity
- **WHEN** the value returned by `comparing()` is passed to `then_comparing()`
- **THEN** its whole ordering is appended with directions intact, unchanged from today

#### Scenario: a null-tolerant comparator is recognised as a comparator
- **WHEN** the value returned by `nulls_first()` or `nulls_last()` over a bare comparator is passed to `then_comparing()`
- **THEN** it contributes a supplied ordering, and elements are ordered by it rather than raising

#### Scenario: a callable of indeterminate arity is treated as a key extractor
- **WHEN** a callable accepting only `*args` is passed to `then_comparing()`
- **THEN** it contributes one ascending key-based ordering

### Requirement: A supplied ordering obeys the Comparator contract
A supplied comparator SHALL be held to the same result contract as any other
`Comparator`: it MUST return an `int`, and returning a `bool` SHALL raise
`TypeError` rather than silently producing an order.

#### Scenario: a bool-returning supplied comparator is rejected
- **WHEN** a chain containing a supplied comparator that returns `bool` is used to sort
- **THEN** `TypeError` is raised

#### Scenario: a bool-returning key comparator is rejected
- **WHEN** `comparing(key_extractor, key_comparator)` whose `key_comparator` returns `bool` is used to sort
- **THEN** `TypeError` is raised

### Requirement: A supplied ordering composes with direction, nulls and stability
A supplied ordering SHALL behave under `reversed()`, under null tolerance, and
under sorting stability exactly as a key-based ordering does. Reversing SHALL
negate a supplied ordering along with every other component. A null-tolerant
comparator SHALL place a `None` *element* at the declared end without invoking
the supplied comparator on it. Sorting SHALL preserve the encounter order of
elements a chain containing a supplied ordering treats as equivalent.

#### Scenario: reversing negates a supplied ordering
- **WHEN** `reversed()` is applied to a chain ending in a supplied comparator
- **THEN** the resulting order is the exact reverse of the unreversed chain's ordering, ties excepted

#### Scenario: reversing before chaining flips only the earlier ordering
- **WHEN** `reversed()` is applied before a supplied comparator is chained on
- **THEN** the earlier ordering is negated and the supplied one is not

#### Scenario: a null element is placed without consulting the supplied comparator
- **WHEN** a null-tolerant chain containing a supplied comparator sorts a list containing `None`
- **THEN** `None` is placed at the declared end and the supplied comparator is never invoked with it

#### Scenario: a chain containing a supplied ordering is stable
- **WHEN** elements the whole chain treats as equivalent are sorted
- **THEN** they appear in encounter order

### Requirement: The sorting path and the direct-comparison path agree
A comparator containing a supplied ordering SHALL produce the same order when
driven through `sorted()` as the order implied by invoking it directly on pairs
of elements. Neither path SHALL be the only one that honours direction, null
placement, or the `int` result contract.

#### Scenario: sorting agrees with pairwise comparison
- **WHEN** a chain containing a supplied ordering is used to sort a list, and the same chain is invoked directly on every pair of that list
- **THEN** the sorted order is consistent with the signs the direct invocations return

#### Scenario: min() and max() agree with sorted()
- **WHEN** a chain containing a supplied ordering is passed to `min()` and `max()`
- **THEN** the elements returned are the first and last of the order `sorted()` produces for the same input
