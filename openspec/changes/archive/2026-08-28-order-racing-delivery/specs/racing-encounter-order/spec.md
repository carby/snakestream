## ADDED Requirements

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
- `count()`, `for_each()`, `find_any()`, `max()`, `min()`, `all_match()`,
  `any_match()` and `none_match()` do NOT observe it and SHALL pay nothing for
  this requirement — neither reorder buffering nor head-of-line delay.
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

### Requirement: An ordered tail races everything after its barrier operation

Where the chain is split at an operation that must see the whole stream in
encounter order, only that operation itself SHALL run in a single ordered pass.
Every operation after it SHALL race across branches again, subject to that
resumed portion's own ordering requirements and to the delivery rule above.

Racing the suffix SHALL NOT change the pipeline's result: a suffix of an
ordered pipeline delivering to an order-observing terminal still delivers in
encounter order, because the delivery barrier applies there too.

An explicit `unordered()` in the tail SHALL no longer be what resumes racing;
it retains its meaning as the declaration that clears the encounter-order
requirement for everything after it, and therefore removes the delivery barrier
from a pipeline that is unordered at its terminal.

#### Scenario: The suffix of a short-circuiting pipeline regains concurrency
- **WHEN** `.parallel().limit(8).map(slow)` is collected, where `slow` sleeps
  per element
- **THEN** the eight mapped elements are produced concurrently rather than one
  at a time, and the result is the first eight elements in encounter order,
  mapped

#### Scenario: A raced suffix still delivers in encounter order
- **WHEN** `.parallel().sorted(asc).map(f).collect(to_list())` is run
- **THEN** the result is the sorted elements, mapped, in sorted order

#### Scenario: A tail that sorts again splits again
- **WHEN** `.parallel().limit(20).map(f).sorted(asc).collect(to_list())` is run
- **THEN** the result is the mapped first twenty elements, fully sorted

#### Scenario: unordered() in the tail removes the delivery barrier
- **WHEN** `.parallel().sorted(asc).unordered().map(f).collect(to_list())` is
  run
- **THEN** the mapped elements arrive in whatever order the race resolves them,
  and the sort still saw the whole stream

## MODIFIED Requirements

### Requirement: An unordered pipeline takes the order-blind path

Where the pipeline carries no encounter-order requirement at an order-sensitive
operation's position, that operation SHALL take the order-blind path: `limit(n)`
yields the first `n` elements to arrive across all branches in whatever order
the race resolves them, `skip(n)` drops the first `n` to arrive, `distinct()`
keeps an arbitrary representative of each equal group, and a sort's output
carries no cross-branch ordering guarantee. These SHALL remain valid results —
`unordered()` is the caller declaring that any of them will do.

Where the pipeline carries no encounter-order requirement at the *end of the
chain*, delivery to the terminal SHALL likewise be order-blind: no reorder
barrier is engaged, whatever the terminal declares about observing order.

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

### Requirement: Read-ahead under an ordered racing pipeline is bounded

Honouring encounter order requires holding a finished element until every
earlier element has been released. The number of elements pulled from the source
but not yet released SHALL be bounded by a fixed window, so that one slow
element cannot cause the remainder of the source to be drawn into memory.

This bound SHALL apply to a delivery barrier exactly as it applies to a barrier
in front of an order-sensitive operation: an ordered racing pipeline whose
terminal observes encounter order SHALL run in memory proportional to the window
and the number of branches, whatever the length of the source.

The bound SHALL hold for an unbounded or very large source: an ordered racing
pipeline over such a source SHALL run in memory proportional to the window and
the number of branches, not to the length of the source. This is subject to the
memory an operation requires by its own definition — `sorted()` buffers its
input whatever the executor — and to what the terminal itself accumulates: a
collector building a list of the whole stream holds the whole stream by its own
definition, not because of the barrier.

A consequence SHALL be accepted and is not a defect: an operation upstream of a
short-circuiting one may run on more elements than the sequential pipeline would
run it on, up to the window. A racing pipeline is permitted this over-pull where
a sequential one is not, matching the existing racing behaviour and Java's
parallel `limit()`. The elements *selected* are unaffected.

#### Scenario: A slow first element does not draw the whole source into memory
- **WHEN** an ordered racing pipeline is run over a large source in which the
  first element's upstream work is far slower than every other element's
- **THEN** the number of elements pulled from the source ahead of the first
  release stays within the window, rather than growing with the source

#### Scenario: A delivery barrier over a large source is bounded too
- **WHEN** `.parallel().map(f).for_each_ordered(...)`-shaped work is replaced by
  an ordered racing pipeline with no order-sensitive operation, delivering to an
  order-observing terminal over a very large source with one slow element at the
  head
- **THEN** the elements pulled ahead of the first release stay within the window

#### Scenario: An ordered racing limit() over an unbounded source terminates
- **WHEN** `.limit(n)` is queued on an ordered racing pipeline over an infinite
  source
- **THEN** the pipeline yields exactly `n` elements, in encounter order, and
  terminates, closing the source

#### Scenario: Over-pull upstream of an ordered limit() is bounded, and selection is not affected
- **WHEN** `.peek(fn).limit(n)` is run on an ordered racing pipeline over a
  source with far more than `n` elements
- **THEN** `fn` may be called more than `n` times but not unboundedly so, and
  the elements yielded are exactly the first `n` in encounter order

### Requirement: Ordering does not change which elements a racing pipeline produces

Honouring encounter order SHALL affect only the order in which elements reach an
order-sensitive operation or the terminal and, through the former, which
elements that operation selects. It SHALL NOT duplicate, drop, or corrupt
elements.

Every source the racing executor accepts today SHALL still be accepted: sync and
async, closeable and not, `__aiter__` returning `self` or a separate iterator.
Pulls from the shared source SHALL remain serialized, and the shared source
SHALL be closed exactly as it is without a barrier — each branch closes it on
its way out, which for the async generators source normalization builds means
its `finally` runs once. Introducing a barrier SHALL NOT change how many times
a closeable source is closed, and a delivery barrier SHALL NOT change it either.

Errors raised by user-supplied callables SHALL still propagate out of the
pipeline rather than being swallowed by a buffer holding elements back.

#### Scenario: A pipeline with no order-sensitive operation is unaffected
- **WHEN** a racing pipeline of only `map`, `filter`, `peek` and `flat_map`
  operations is collected
- **THEN** it yields the same elements as a multiset that it does today, now in
  encounter order where the terminal observes order

#### Scenario: Every element appears exactly once
- **WHEN** an ordered racing pipeline containing an order-sensitive operation is
  collected over a source with repeated and distinguishable elements
- **THEN** each element the operation admits appears exactly once, none is lost,
  and none is duplicated

#### Scenario: A barrier does not change how the shared source is closed
- **WHEN** the same short-circuiting racing pipeline is run with a barrier and
  without one, over a closeable source that counts its closes
- **THEN** the two counts are equal, and a generator source behind a barrier
  runs its `finally` exactly once

#### Scenario: A delivery barrier does not change how the shared source is closed
- **WHEN** an ordered racing pipeline with no order-sensitive operation is run
  to an order-observing terminal and to an order-blind one, over a closeable
  source that counts its closes
- **THEN** the two counts are equal

#### Scenario: A source with no aclose() still races under an ordered pipeline
- **WHEN** an ordered racing pipeline containing an order-sensitive operation is
  run over an object implementing `__aiter__`/`__anext__` but no `aclose()`
- **THEN** it yields exactly the elements that object produces, with no
  `AttributeError`

#### Scenario: An error in an upstream callable propagates rather than deadlocking
- **WHEN** a mapping operation upstream of an order-sensitive operation raises on
  one element of an ordered racing pipeline
- **THEN** that exception propagates out of the terminal operation, and the
  pipeline does not hang waiting for the element that failed

#### Scenario: An error under a delivery barrier propagates rather than deadlocking
- **WHEN** a mapping operation raises on one element of an ordered racing
  pipeline with no order-sensitive operation, delivering to an order-observing
  terminal
- **THEN** that exception propagates out of the terminal operation, and the
  pipeline does not hang
