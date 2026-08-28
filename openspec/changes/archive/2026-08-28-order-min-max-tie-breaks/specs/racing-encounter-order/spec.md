## MODIFIED Requirements

### Requirement: A racing pipeline delivers in encounter order when its terminal observes it

Where a terminal operation observes the encounter order of the elements it
receives, and the pipeline carries an encounter-order requirement at the end of
the chain, the racing executor SHALL deliver elements to that terminal in
encounter order. The result SHALL equal the result the same pipeline produces
under the sequential executor.

This SHALL hold whether or not the chain contains an order-sensitive operation:
a chain of only `map`, `filter`, `peek` and `flat_map` delivers in encounter
order under `.parallel()` exactly as one containing `sorted()` does.

A terminal operation SHALL declare whether it observes encounter order:

- `collect(collector)` observes it unless the collector declares
  `Characteristics.UNORDERED`.
- `collect(supplier, accumulator, combiner)`, `reduce()`, `to_array()`,
  `collect(to_generator)` and `iterator()` observe it.
- `max()` and `min()` observe it. Their *value* is the same in any order, but
  which of two equal-comparing distinguishable elements they return is not, and
  `comparator-contract` requires the first in encounter order. They take the
  cheapest split there is — at `len(chain)`, so every operation still races and
  only delivery is ordered — and `unordered()` releases them from it.
- `count()`, `for_each()`, `find_any()`, `all_match()`, `any_match()` and
  `none_match()` do NOT observe it and SHALL pay nothing for this requirement —
  neither reorder buffering nor head-of-line delay.
- `find_first()` and `for_each_ordered()` are unaffected: each names the
  sequential executor at its own call site as it does today, per the
  `stream-execution-model` capability.

Restoring order for delivery SHALL NOT serialize the chain. Every operation in
the chain SHALL still run across all branches concurrently; only the handing of
finished elements to the terminal is ordered.

#### Scenario: An ordered racing map/filter pipeline collects in encounter order
- **WHEN** a stream over `range(50)` queues a mapping operation with variable
  per-element cost and is run under `.parallel()` and collected with
  `to_list()`
- **THEN** the result is the mapped elements in source order, equal to the
  sequential pipeline's result

#### Scenario: Delivery ordering does not serialize the chain
- **WHEN** an ordered racing pipeline whose mapping operation sleeps per element
  is collected with `to_list()`
- **THEN** it completes in substantially less wall-clock time than the
  sequential pipeline over the same source, because the mapping still runs
  across all branches concurrently

#### Scenario: reduce() over an ordered racing pipeline folds in encounter order
- **WHEN** `.parallel()` is used with a non-commutative accumulator, for
  instance folding elements into a string
- **THEN** the result equals the sequential fold

#### Scenario: An ordered racing max() breaks ties in encounter order
- **WHEN** `max()` or `min()` is awaited on an ordered racing pipeline over
  records whose comparator keys tie
- **THEN** the result is the tied record earliest in encounter order, equal to
  the sequential pipeline's result

#### Scenario: An order-blind terminal pays nothing
- **WHEN** `count()`, `for_each()`, `any_match()` or `find_any()` is called on
  an ordered racing pipeline
- **THEN** no element is held back waiting for an earlier one, and the pipeline
  behaves exactly as it does without this requirement

#### Scenario: An UNORDERED collector takes the order-blind path
- **WHEN** an ordered racing pipeline is collected with `to_set()`, which
  declares `Characteristics.UNORDERED`
- **THEN** no delivery barrier is engaged, and the collected set is correct

#### Scenario: An unordered pipeline delivers unordered
- **WHEN** `.parallel().unordered().map(f).collect(to_list())` is run
- **THEN** elements may arrive in any order, no delivery barrier is engaged, and
  the collected list is the mapped elements as a multiset

#### Scenario: unordered() after an order-sensitive operation still clears delivery
- **WHEN** `.parallel().limit(5).unordered().map(f).collect(to_list())` is run
- **THEN** `limit(5)` still selects the first five in encounter order, and
  delivery of the mapped results carries no ordering guarantee

### Requirement: An unordered pipeline takes the order-blind path

Where the pipeline carries no encounter-order requirement at an order-sensitive
operation's position, that operation SHALL take the order-blind path: `limit(n)`
yields the first `n` elements to arrive across all branches in whatever order
the race resolves them, `skip(n)` drops the first `n` to arrive, and
`distinct()` keeps an arbitrary representative of each equal group. These SHALL
remain valid results — `unordered()` is the caller declaring that any of them
will do.

`sorted()` is the exception and SHALL NOT take this path. A sort claims its
output is ordered, so it SHALL see the whole stream in encounter order wherever
it sits, regardless of the ordering characteristic at its own position; a sort
left in the raced head would sort each branch's subset. Its output is therefore
ordered, and stable, on an unordered pipeline as on an ordered one — see
`comparator-contract`.

Where the pipeline carries no encounter-order requirement at the *end of the
chain*, delivery to the terminal SHALL likewise be order-blind: no reorder
barrier is engaged, whatever the terminal declares about observing order. This
covers `max()`/`min()`, which observe encounter order on an ordered pipeline and
release it here.

No ordering machinery SHALL be engaged on such a pipeline: the per-element cost
and the memory profile of an unordered racing pipeline SHALL be unchanged by
this capability.

`unordered()` therefore SHALL be a performance lever and not only a semantic
one: on any racing pipeline delivering to an order-observing terminal, and on
any pipeline containing an order-sensitive operation, declaring the pipeline
unordered SHALL admit concurrency that the ordered form cannot. This SHALL be
measurable and SHALL be measured.

#### Scenario: An unordered limit() takes the first n to arrive
- **WHEN** `.unordered()` is queued before a mapping operation with variable
  per-element cost and `.limit(5)`, under `.parallel()`
- **THEN** the result is five elements of the source, not necessarily the first
  five in encounter order, and no error is raised

#### Scenario: An unordered sort still sorts the whole stream
- **WHEN** `.parallel().unordered().sorted(c)` is collected
- **THEN** the result is every source element in the comparator's order, not a
  concatenation of per-branch sorted subsets

#### Scenario: An unordered pipeline pays no ordering cost
- **WHEN** a racing pipeline containing an order-sensitive operation is run with
  `.unordered()` queued before that operation, and again without it
- **THEN** the unordered run holds no elements back waiting for an earlier one
  and completes without the ordered run's head-of-line delay

#### Scenario: An unordered pipeline with no order-sensitive operation pays no delivery cost
- **WHEN** `.parallel().unordered().map(f).collect(to_list())` is run and again
  without the `.unordered()`
- **THEN** the unordered run engages no reorder buffer and holds no element back

#### Scenario: unordered() applies only to operations queued after it
- **WHEN** an order-sensitive operation is queued **before** `.unordered()`
- **THEN** that operation still honours encounter order, because the pipeline is
  ordered at its position

#### Scenario: sorted() re-imposes the requirement for what follows
- **WHEN** `.unordered()` is queued, then `.sorted(asc)`, then `.limit(3)`,
  under `.parallel()`
- **THEN** the `limit(3)` yields the three smallest elements under the
  comparator, because the sort restored the encounter-order requirement at that
  position

#### Scenario: An unordered max() pays no ordering cost
- **WHEN** `.parallel().unordered().max(c)` is awaited
- **THEN** no delivery barrier is engaged, no element is held back waiting for
  an earlier one, and the returned value is correct
