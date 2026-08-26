## Purpose

Defines what encounter order means under the racing executor: how order is
preserved across branches that finish out of order, which operations require it,
where in a pipeline the requirement takes effect, and what it costs. Racing
destroys encounter order at the merge, so an operation whose answer depends on
global position — `sorted()`, `limit()`, `skip()`, `distinct()` — needs order
restored before it decides. This capability is the contract for that
restoration, and for the deliberate absence of it on an unordered pipeline,
where the cheaper order-blind behaviour is correct and is what runs.

## ADDED Requirements

### Requirement: Order-sensitive operations honour encounter order under the racing executor

An operation whose result depends on an element's position in the stream —
`sorted()`, `limit(n)`, `skip(n)` and `distinct()` — SHALL produce the same
result under the racing executor as under the sequential executor whenever the
pipeline carries an encounter-order requirement at that operation's position.

This SHALL hold regardless of how much per-element work sits upstream of the
operation and regardless of how unevenly that work is distributed: an operation
upstream of `limit(5)` that is slow for the first five elements and fast for the
rest SHALL NOT cause a later element to take a slot from an earlier one.

Sameness is on the elements selected and their order, not on how many times an
upstream operation ran; see the read-ahead requirement below.

#### Scenario: limit() selects the first n in encounter order despite variable upstream cost
- **WHEN** a stream over `range(12)` queues a mapping operation that is slow for
  the first five elements and fast for the rest, then `.limit(5)`, and is run
  under `.parallel()` and collected
- **THEN** the result is `[0, 1, 2, 3, 4]`, the same list the sequential
  pipeline produces

#### Scenario: skip() drops the first n in encounter order despite variable upstream cost
- **WHEN** the same stream queues that mapping operation, then `.skip(5)`, and
  is run under `.parallel()` and collected
- **THEN** the elements `0` through `4` are the ones dropped, and every element
  from `5` onward is present

#### Scenario: sorted() sorts the whole stream, not each branch's subset
- **WHEN** a stream built from an **async** source yielding `12, 11, ..., 1`
  queues `.sorted(asc)` and is run under `.parallel()` and collected
- **THEN** the result is `[1, 2, ..., 12]`

#### Scenario: sorted() under racing sorts across branches for a sync source too
- **WHEN** the same pipeline is built from a list source rather than an async one
- **THEN** the result is likewise fully sorted, and is so because the ordering
  requirement was honoured rather than because one branch happened to take
  every element

#### Scenario: distinct() keeps the earliest-encountered duplicate
- **WHEN** a stream over objects that compare equal but are distinguishable
  queues `.distinct()` and is run under `.parallel()`
- **THEN** the survivor of each equal group is the one earliest in encounter
  order, matching the sequential result

#### Scenario: An order-sensitive operation queued before .parallel() is still honoured
- **WHEN** `.sorted(asc)` (or `.limit(n)`, `.skip(n)`, `.distinct()`) is queued
  before the `.parallel()` call that selects the racing executor
- **THEN** it honours encounter order exactly as it does when queued after the
  switch, because the executor governs the whole pipeline

### Requirement: An unordered pipeline takes the order-blind path

Where the pipeline carries no encounter-order requirement at an order-sensitive
operation's position, that operation SHALL take the order-blind path: `limit(n)`
yields the first `n` elements to arrive across all branches in whatever order
the race resolves them, `skip(n)` drops the first `n` to arrive, `distinct()`
keeps an arbitrary representative of each equal group, and a sort's output
carries no cross-branch ordering guarantee. These SHALL remain valid results —
`unordered()` is the caller declaring that any of them will do.

No ordering machinery SHALL be engaged on such a pipeline: the per-element cost
and the memory profile of an unordered racing pipeline SHALL be unchanged by
this capability.

`unordered()` therefore SHALL be a performance lever and not only a semantic
one: on a pipeline containing an order-sensitive operation, declaring the
pipeline unordered SHALL admit concurrency that the ordered form cannot.

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

The bound SHALL hold for an unbounded or very large source: an ordered racing
pipeline over such a source SHALL run in memory proportional to the window and
the number of branches, not to the length of the source. This is subject to the
memory an operation requires by its own definition — `sorted()` buffers its
input whatever the executor.

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
order-sensitive operation and, through it, which elements that operation
selects. It SHALL NOT duplicate, drop, or corrupt elements, and SHALL NOT change
the elements produced by a pipeline containing no order-sensitive operation.

Every source the racing executor accepts today SHALL still be accepted: sync and
async, closeable and not, `__aiter__` returning `self` or a separate iterator.
Pulls from the shared source SHALL remain serialized, and the shared source
SHALL be closed exactly as it is without a barrier — each branch closes it on
its way out, which for the async generators source normalization builds means
its `finally` runs once. Introducing a barrier SHALL NOT change how many times
a closeable source is closed.

Errors raised by user-supplied callables SHALL still propagate out of the
pipeline rather than being swallowed by a buffer holding elements back.

#### Scenario: A pipeline with no order-sensitive operation is unaffected
- **WHEN** a racing pipeline of only `map`, `filter`, `peek` and `flat_map`
  operations is collected
- **THEN** it yields the same elements as a multiset that it does today, under
  the same behaviour

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
