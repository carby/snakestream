## Purpose

Defines how a stream's execution mode is carried and applied: an executor value
held by the stream, a two-method executor protocol, which executor a terminal
uses, the rule that the one terminal requiring encounter order regardless of
the stream's mode — `find_first()` — names its executor explicitly instead of
depending on the stream's, and the second axis alongside it: whether a terminal observes encounter order at all, which is what decides
whether the executor owes it.

## Requirements

### Requirement: Execution mode is a value carried by the stream

A stream SHALL hold its execution mode as a value (an executor), not as its
type. There SHALL be exactly one sequential executor and one racing executor,
and a stream SHALL carry exactly one of them at any time. No stream subclass
SHALL exist for the purpose of encoding execution mode.

`is_parallel()` SHALL report the mode from that value.

#### Scenario: A sequentially-built stream reports sequential
- **WHEN** `Stream.of([1, 2, 3]).is_parallel()` is called
- **THEN** the result is `False`

#### Scenario: A parallel stream reports parallel
- **WHEN** `Stream.of([1, 2, 3]).parallel().is_parallel()` is called
- **THEN** the result is `True`

#### Scenario: Intermediate operations carry the executor forward
- **WHEN** an intermediate operation is called on a parallel stream
- **THEN** the returned stream reports `is_parallel()` as `True`

#### Scenario: A user subclass survives a mode switch
- **WHEN** `.parallel()` and then `.sequential()` are called on an instance of a
  user-defined `class MyStream(Stream)`
- **THEN** each returned instance is a `MyStream`, not a plain `Stream`, matching
  how intermediate operations already preserve subclass identity

### Requirement: The executor protocol has exactly two operations

An executor SHALL expose exactly two operations over a chain and a source: one
producing an `AsyncGenerator` of the chain's output elements, and one driving
the chain into a terminal sink and returning that sink's result.

Both operations SHALL accept, alongside the chain and the source, the caller's
declaration of whether the consumer observes encounter order. The
element-producing operation's consumer is whoever iterates the generator and
always observes it; the terminal-driving operation's consumer is the terminal
sink, which declares for itself. An executor for which the declaration makes no
difference — the sequential one, which is ordered by construction — SHALL accept
it and ignore it.

The element-producing operation SHALL be the one used by `iterator()`,
`collect(to_generator)`, `Stream.concat()` and the mode switches. The
terminal-driving operation SHALL be the one used by every other terminal
operation.

The terminal-driving operation SHALL have a single generic implementation —
driving the element-producing operation's output into the terminal — which the
racing executor uses unchanged. The sequential executor MAY override it with a
fused implementation that pushes source elements through the chain straight into
the terminal with nothing buffered on the way; that override SHALL be a
performance specialization only, producing results indistinguishable from the
generic implementation.

An executor's element-producing operation MAY internally run different parts of
the chain differently — for instance racing the operations upstream of an
ordering barrier while running the barrier operation itself in a single ordered
pass and racing everything after it, or reordering only the delivery of a chain
raced end to end (see the `racing-encounter-order` capability). Such an internal
split SHALL NOT constitute a third executor, SHALL NOT be selectable or
observable as a mode, and SHALL leave `is_parallel()` reporting the executor the
stream carries.

#### Scenario: Both executors produce the same elements
- **WHEN** the same chain over the same source is composed to a generator under
  the sequential executor and under the racing executor
- **THEN** both yield the same elements, subject only to the ordering guarantee
  each mode already gives

#### Scenario: The fused override is indistinguishable from the generic form
- **WHEN** a terminal operation is driven under the sequential executor
- **THEN** its result equals what driving the composed generator into the same
  terminal sink would have produced

#### Scenario: The sequential executor ignores the ordering declaration
- **WHEN** a chain is run under the sequential executor with the consumer
  declaring that it observes encounter order, and again declaring that it does
  not
- **THEN** both runs produce identical results, in encounter order

#### Scenario: An internal ordering barrier is not a mode
- **WHEN** a racing pipeline containing an order-sensitive operation on an
  ordered chain is run, so that part of the chain runs in a single ordered pass
- **THEN** `is_parallel()` still reports `True`, and there are still exactly two
  executor values in the package

#### Scenario: A delivery barrier is not a mode either
- **WHEN** an ordered racing pipeline with no order-sensitive operation is
  collected by an order-observing terminal, so that delivery is reordered
- **THEN** `is_parallel()` still reports `True`, and there are still exactly two
  executor values in the package

### Requirement: A terminal uses the stream's executor unless it names one, and only find_first() names one

A terminal operation SHALL execute under the executor its stream carries.

A terminal operation SHALL additionally declare whether it observes the
encounter order of the elements it receives. This is a second, independent axis
alongside which executor it names: the executor decides *how* the chain runs,
the declaration decides whether the executor must deliver in encounter order
(see the `racing-encounter-order` capability). Under the sequential executor the
declaration changes nothing.

`count()`, `for_each()`, `find_any()`, `max()`, `min()`, `all_match()`,
`any_match()` and `none_match()` SHALL declare that they do not observe it.
`reduce()`, `to_array()`, `for_each_ordered()` and the three-argument
`collect(supplier, accumulator, combiner)` SHALL declare that they do.
`collect(collector)` SHALL derive its declaration from the collector: it
observes encounter order unless the collector declares
`Characteristics.UNORDERED`.

A terminal operation whose contract requires encounter order regardless of the
stream's mode SHALL name the sequential executor explicitly at its call site,
rather than relying on a shared implementation that is promised never to be
overridden.

`find_first()` SHALL do this **unconditionally**, without consulting the
ordering characteristic. Java does not relax `findFirst()` on an unordered
stream either: `FindOp.mustFindFirst` is fixed when the operation is
constructed, and the leftmost scan runs whenever it is set. The javadoc permits
returning any element there; the implementation declines to, and so does this
one. `find_any()` is where a caller who wants the race goes.

`for_each_ordered()` SHALL NOT do this. Its encounter-order guarantee is
satisfied by the delivery barrier the racing executor already provides to every
order-observing terminal, so it declares that it observes encounter order and
otherwise follows the stream's own executor in both the ordered and the
unordered case; see the `stream-foreach-ordered` capability.

#### Scenario: An ordinary terminal follows the stream's executor
- **WHEN** `count()` is called on a parallel stream
- **THEN** the chain is driven under the racing executor

#### Scenario: An order-blind terminal declares so
- **WHEN** `count()`, `for_each()`, `any_match()` or `find_any()` is called on an
  ordered parallel stream
- **THEN** no reorder barrier is engaged and no element is held back waiting for
  an earlier one

#### Scenario: An order-observing terminal declares so
- **WHEN** `reduce()`, `to_array()` or `collect(to_list())` is called on an
  ordered parallel stream
- **THEN** elements reach the terminal in encounter order

#### Scenario: collect() takes its declaration from the collector
- **WHEN** the same ordered parallel stream is collected with `to_list()` and
  with `to_set()`, which declares `Characteristics.UNORDERED`
- **THEN** the `to_list()` collection engages the reorder barrier and the
  `to_set()` collection does not

#### Scenario: for_each_ordered follows the stream's executor when ordered
- **WHEN** `for_each_ordered(consumer)` is called on an ordered parallel stream
- **THEN** the chain is driven under the racing executor, the reorder barrier is
  engaged, and the consumer is invoked in encounter order

#### Scenario: for_each_ordered follows the stream's executor when unordered
- **WHEN** `for_each_ordered(consumer)` is called on a parallel stream marked
  `unordered()`
- **THEN** the chain is driven under the racing executor with no reorder barrier
  engaged, and the consumer is invoked once per element

#### Scenario: find_first on an ordered parallel stream ignores the stream's executor
- **WHEN** `find_first()` is called on an ordered parallel stream
- **THEN** the chain is driven under the sequential executor and the true first
  element in encounter order is returned

#### Scenario: find_first on an unordered stream still forces sequential
- **WHEN** `find_first()` is called on a stream marked `unordered()`
- **THEN** it still runs under the sequential executor and returns the first
  element in the source's encounter order, rather than behaving as `find_any()`

#### Scenario: find_any remains the unordered alternative
- **WHEN** `find_any()` is called on a parallel stream
- **THEN** it runs under the stream's own executor and may return any element

### Requirement: PROCESSES is part of the package's public export surface

`PROCESSES`, the tunable worker count the racing executor is built from, SHALL
be importable directly from the top-level `snakestream` package, not only from
`snakestream.execution`.

#### Scenario: PROCESSES is importable from the top-level package

- **WHEN** a caller writes `from snakestream import PROCESSES`
- **THEN** the import succeeds and yields the same `int` value as
  `snakestream.execution.PROCESSES`

### Requirement: Source acceptance does not depend on execution mode

The set of source values a stream accepts and can consume SHALL be identical in
both execution modes. Any source a sequentially-executed pipeline consumes
successfully SHALL be consumed successfully by the same pipeline under
`.parallel()`, producing the same elements as a multiset. No source SHALL raise
an error in one mode that it does not raise in the other.

In particular, an async source SHALL NOT be required to be a full async
generator. An `AsyncIterable` is accepted whether or not it exposes `aclose()`,
and whether or not its `__aiter__()` returns itself: a racing branch SHALL
obtain its iterator through the same protocol a sequential pass uses, and SHALL
close the source only if the source is closeable.

Ordering is not a difference between the modes on an ordered pipeline
delivering to an order-observing consumer: both deliver in encounter order. On
an unordered pipeline, or to an order-blind terminal, the racing mode does not
preserve encounter order, so the comparison of results between modes is
order-insensitive there.

#### Scenario: Racing over an async iterator with no aclose()
- **WHEN** a stream is constructed from an object implementing `__aiter__` (returning itself) and `__anext__` but no `aclose()`, and is consumed with `.parallel()`
- **THEN** the stream yields exactly the elements the object produces, with no `AttributeError`, and the same elements the sequential consumption of an identical source yields

#### Scenario: Racing over a source whose `__aiter__` returns a separate iterator
- **WHEN** a stream is constructed from an object whose `__aiter__` returns a distinct iterator rather than `self`, and is consumed with `.parallel()`
- **THEN** the stream yields exactly the elements that iterator produces, with no `AttributeError`

#### Scenario: A closeable source is still closed under racing
- **WHEN** a stream constructed from an async generator is consumed with `.parallel()`
- **THEN** the async generator is closed by the time consumption finishes, as it is under sequential consumption

#### Scenario: Sync and scalar sources race identically
- **WHEN** a stream constructed from a list, a bare sync iterator, or a scalar value is consumed with `.parallel()`
- **THEN** it yields the same elements, as a multiset, as the same stream consumed sequentially
