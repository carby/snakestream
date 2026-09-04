## Purpose

Defines how a stream's execution mode is carried and applied: an executor value
held by the stream, a two-method executor protocol, which executor a terminal
uses — always the stream's own, since no terminal names one for itself — and
the second axis alongside it: what a terminal demands of encounter order, which
is what decides whether the executor owes it. That demand is three-valued rather
than a bool, because `find_first()` asks unconditionally where every other
order-observing terminal asks only where the pipeline is ordered.

## Requirements

### Requirement: Execution mode is a value carried by the stream

A stream SHALL hold its execution mode as a value (an executor), not as its
type. There SHALL be exactly one sequential executor and one fork-join
executor, and a stream SHALL carry exactly one of them at any time. No stream
subclass SHALL exist for the purpose of encoding execution mode.

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
fork-join executor uses unchanged. The sequential executor MAY override it with
a fused implementation that pushes source elements through the chain straight
into the terminal with nothing buffered on the way; that override SHALL be a
performance specialization only, producing results indistinguishable from the
generic implementation.

The fork-join executor's use of the generic form is not only a measurement
result, as it is for the sequential executor: each batch builds and runs its
own sink chain on its own OS thread, torn down once the batch finishes, so
there is no single, long-lived chain instance a terminal could be fused onto
the way the sequential executor fuses onto its one chain. Fusing the terminal
into fork-join's per-batch chains would require the terminal sink itself to
accumulate correctly across concurrently-running batches — exactly the
`Collector` combiner this library does not yet drive (see `collector.py`'s
`combiner`, unused pending a future change) — so the generic
compose-then-drain form remains the only option here, not merely the cheaper
one.

An executor's element-producing operation MAY internally run different parts of
the chain differently — for instance running batches concurrently upstream of
an ordering barrier while running the barrier operation itself in a single
ordered pass and running everything after it concurrently again, or reordering
only the delivery of a chain that ran concurrently end to end (see the
`racing-encounter-order` capability). Such an internal split SHALL NOT
constitute a third executor, SHALL NOT be selectable or observable as a mode,
and SHALL leave `is_parallel()` reporting the executor the stream carries.

#### Scenario: Both executors produce the same elements
- **WHEN** the same chain over the same source is composed to a generator under
  the sequential executor and under the fork-join executor
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
- **WHEN** a parallel pipeline containing an order-sensitive operation on an
  ordered chain is run, so that part of the chain runs in a single ordered pass
- **THEN** `is_parallel()` still reports `True`, and there are still exactly two
  executor values in the package

#### Scenario: A delivery barrier is not a mode either
- **WHEN** an ordered parallel pipeline with no order-sensitive operation is
  collected by an order-observing terminal, so that delivery is reordered
- **THEN** `is_parallel()` still reports `True`, and there are still exactly two
  executor values in the package

### Requirement: A terminal follows the stream's executor and declares what it observes

A terminal operation SHALL execute under the executor its stream carries. No
terminal SHALL name an executor for itself.

A terminal operation SHALL declare whether it observes the encounter order of
the elements it receives. This is a second, independent axis alongside the
executor the stream carries: the executor decides *how* the chain runs, the
declaration decides whether the executor must deliver in encounter order (see
the `racing-encounter-order` capability). Under the sequential executor the
declaration changes nothing.

The declaration SHALL be three-valued, because a terminal's demand for
encounter order can be unconditional or conditional on the pipeline being
ordered, and a two-valued declaration cannot express the first:

- Terminals that do not observe it: `count()`, `for_each()`, `find_any()`,
  `max()`, `min()`, `all_match()`, `any_match()` and `none_match()`. They SHALL
  pay nothing — neither reorder buffering nor head-of-line delay — subject to
  the bounded same-batch exception the `racing-encounter-order` capability
  documents for a short-circuiting one of these under the fork-join executor.
- Terminals that observe it **when the pipeline is ordered**: `reduce()`,
  `to_array()`, `for_each_ordered()`, `iterator()` and the three-argument
  `collect(supplier, accumulator, combiner)`. `collect(collector)` SHALL derive
  its declaration from the collector — it observes encounter order unless the
  collector declares `Characteristics.UNORDERED`.
- Terminals that observe it **unconditionally**, whatever the pipeline's
  ordering characteristic: `find_first()`, and no other.

`find_first()`'s unconditional demand SHALL restore encounter order for
delivery only, and SHALL NOT constrain how the chain runs. Java does not relax
`findFirst()` on an unordered stream: `FindOp.mustFindFirst` is fixed when the
operation is constructed, and the leftmost scan runs whenever it is set. The
javadoc permits returning any element there; the implementation declines to, and
so does this one — and, like `FindTask`, it declines without abandoning
parallelism. `find_any()` is where a caller who wants the race goes.

#### Scenario: An ordinary terminal follows the stream's executor
- **WHEN** `count()` is called on a parallel stream
- **THEN** the chain is driven under the fork-join executor

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

#### Scenario: A conditional observer is released by unordered()
- **WHEN** `reduce()` or `for_each_ordered()` is called on a parallel stream
  marked `unordered()`
- **THEN** no reorder barrier is engaged

#### Scenario: find_first is not released by unordered()
- **WHEN** `find_first()` is called on a parallel stream marked `unordered()`
- **THEN** the reorder barrier is still engaged and the first element in the
  source's encounter order is returned, rather than behaving as `find_any()`

#### Scenario: find_first follows the stream's executor
- **WHEN** `find_first()` is called on a parallel stream
- **THEN** the chain is driven under the fork-join executor, every operation
  runs across all batches, and the true first element in encounter order is
  returned

#### Scenario: find_any remains the unordered alternative
- **WHEN** `find_any()` is called on a parallel stream
- **THEN** it runs under the stream's own executor and may return any element

### Requirement: Source acceptance does not depend on execution mode

The set of source values a stream accepts and can consume SHALL be identical in
both execution modes. Any source a sequentially-executed pipeline consumes
successfully SHALL be consumed successfully by the same pipeline under
`.parallel()`, producing the same elements as a multiset. No source SHALL raise
an error in one mode that it does not raise in the other.

In particular, an async source SHALL NOT be required to be a full async
generator. An `AsyncIterable` is accepted whether or not it exposes `aclose()`,
and whether or not its `__aiter__()` returns itself: the pipeline SHALL obtain
its iterator through the same protocol a sequential pass uses — `aiter()` on
the raw source once, up front, before any batch is dispatched, rather than one
per batch — and SHALL close the source only if the source is closeable.

Ordering is not a difference between the modes on an ordered pipeline
delivering to an order-observing consumer: both deliver in encounter order. On
an unordered pipeline, or to an order-blind terminal, the parallel mode does not
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
