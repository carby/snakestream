# comparator-chaining Specification

## Purpose

Defines how key-based comparators compose — chaining a tie-break ordering onto
an existing one, and reversing an ordering's direction — matching Java's
`Comparator.thenComparing` and `Comparator.reversed`. Composition is what makes
multi-key ordering ("department ascending, then salary descending") expressible
without collapsing it into a single hand-written key, and it keeps the
one-extraction-per-element property that key-based ordering exists for.

## Requirements

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

### Requirement: A key-based comparator can be reversed
The value `comparing()` returns SHALL expose a `reversed()` operation producing
a comparator whose ordering is the negation of the receiver's. Reversal SHALL
apply to the receiver's ordering as a whole at the point it is called, so an
ordering chained on afterwards is unaffected by it. Reversal SHALL be
comparator negation, not output reversal: elements the ordering treats as
equivalent SHALL retain their encounter order.

#### Scenario: reversing a single ordering
- **WHEN** `[1, 3, 2]` is sorted by a reversed key-based comparator over the identity key
- **THEN** the result is `[3, 2, 1]`

#### Scenario: reversal applies only to what precedes it
- **WHEN** elements are sorted by an ordering on the first key reversed and then chained with an ordering on the second key
- **THEN** the first key orders descending and the second key orders ascending

#### Scenario: reversal after chaining negates the whole composite
- **WHEN** elements are sorted by an ordering on the first key chained with an ordering on the second key, and the result is then reversed
- **THEN** both keys order descending, and the result is the reverse of the unreversed ordering's result up to the ordering of equivalent elements

#### Scenario: reversal preserves encounter order for equivalent elements
- **WHEN** `[("a", 1), ("b", 1), ("c", 0)]` is sorted by a reversed ordering on the second field
- **THEN** the result is `[("a", 1), ("b", 1), ("c", 0)]` — the two equivalent elements keep their encounter order rather than being swapped

#### Scenario: reversing twice restores the original ordering
- **WHEN** a comparator is reversed twice and used to sort
- **THEN** the result is identical to sorting with the original comparator

### Requirement: Composition produces new comparators and never mutates
`then_comparing()` and `reversed()` SHALL each return a new comparator and SHALL
NOT alter the receiver. A comparator held in a variable and composed in two
different ways SHALL yield two independent orderings, and SHALL itself keep the
ordering it had.

#### Scenario: the receiver is unchanged after composition
- **WHEN** a comparator is bound to a name, `then_comparing()` is called on it, and the original name is then used to sort
- **THEN** the sort uses only the original ordering, with no trace of the appended one

#### Scenario: two compositions of one comparator are independent
- **WHEN** one comparator is composed with two different tie-break orderings
- **THEN** each result orders by its own tie-break only, and neither is affected by the other

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

### Requirement: Sorting extracts each segment's key once per element
When a chained comparator is used to sort, each segment's key extractor SHALL be
invoked exactly once per element — never once per comparison — so a chain of k
segments over n elements costs exactly k×n extractions regardless of how many
comparisons the sort makes.

#### Scenario: each extractor's invocation count is linear in stream length
- **WHEN** a stream of n elements is sorted with a chain of k invocation-counting extractors
- **THEN** each of the k extractors has been invoked exactly n times once the sort completes

### Requirement: A chain's async extractions are concurrent across segments
When a chained comparator with async key extractors is used to sort, the
extractions SHALL be awaited concurrently both across elements and across
segments, rather than one segment's column being resolved before the next
begins. This is the property that a hand-written tuple key cannot express, since
a tuple literal cannot await and an `async def` equivalent resolves its keys in
sequence.

#### Scenario: k async columns do not serialize
- **WHEN** a stream is sorted with a chain of k `async def` extractors that each await an I/O-like delay
- **THEN** the sort's elapsed time is on the order of one delay, not k×n delays or k sequential rounds of n

### Requirement: Keys within a segment must be mutually comparable
Each segment SHALL order on its own keys independently, and SHALL raise
`TypeError` when two keys within one segment do not support comparison with each
other. Keys from different segments are never compared with one another, so
segments MAY produce unrelated key types.

#### Scenario: incomparable keys within one segment raise TypeError
- **WHEN** a chain is used to sort and one segment's extractor yields keys of mutually incomparable types for two elements
- **THEN** a `TypeError` is raised

#### Scenario: segments may produce unrelated key types
- **WHEN** a chain's first segment yields strings and its second yields integers
- **THEN** the sort succeeds, ordering by string then by integer
