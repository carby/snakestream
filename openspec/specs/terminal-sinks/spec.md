## Purpose

Defines how a stream's terminal operations execute: as terminal sinks fed by the same push protocol the intermediate operations use, driven by a loop that pushes source elements through the chain and returns the terminal's finished result — rather than pulling elements out of a composed `AsyncGenerator`. Covers what a short-circuiting terminal is entitled to do (request cancellation so upstream operations stop) and which terminals still go through a generator. It no longer covers an ordered single-flight drive: that existed for `for_each_ordered()` and `find_first()`, and both now obtain encounter order from the racing executor's delivery barrier instead, which the `racing-encounter-order` capability specifies. No terminal names an executor for itself.

## Requirements

### Requirement: Terminal operations are driven as terminal sinks

The terminal operations `reduce()`, `count()`, `for_each()`,
`for_each_ordered()`, `all_match()`, `any_match()`, `none_match()`, `max()`,
`min()`, `find_first()`, `find_any()` and the three-argument mutable-reduction
form of `collect()` SHALL each be executed by constructing a terminal sink,
linking the stream's queued intermediate operations onto it, pushing every
element from the source through that chain into the terminal sink, and
returning the terminal sink's finished result.

The elements a terminal sink observes SHALL be exactly the elements — in
exactly the order — that consuming the same stream's composed generator would
produce.

An element pushed to a terminal SHALL NOT be buffered into an intermediate
container and re-pulled on its way there: the chain's last intermediate sink
SHALL push directly into the terminal sink.

#### Scenario: A terminal's result matches the generator-based equivalent
- **WHEN** any of the listed terminal operations is called on a stream with any chain of intermediate operations
- **THEN** it returns the value that folding the same operation over the same stream's composed generator produces, for the same source and the same chain

#### Scenario: A terminal over an empty source returns its empty result
- **WHEN** any of the listed terminal operations is called on a stream whose source yields no elements
- **THEN** it returns that operation's documented empty-source result (for example `0` from `count()`, `None` from `find_any()`, `True` from `all_match()`) without error

#### Scenario: An async user callable in a terminal is awaited
- **WHEN** a terminal operation is given an async consumer, predicate, comparator or accumulator
- **THEN** that callable is awaited per element, with the same sync-or-async dispatch behavior every other user-supplied callable in the library has

#### Scenario: Terminals reject an already-consumed stream
- **WHEN** a terminal operation is called on a stream reference that has already been extended into a new instance
- **THEN** it raises `IllegalStateException`

### Requirement: Short-circuiting terminals request cancellation upstream

A terminal operation whose result becomes fixed before the source is exhausted
— `find_first()`, `find_any()`, `any_match()`, `all_match()`, `none_match()` —
SHALL report `cancellation_requested()` as `True` from the point its result is
fixed. The loop driving the chain SHALL observe that report through the head
sink and stop pulling from the source, and every intermediate sink between the
terminal and the source SHALL observe it through the same query.

Upstream operations that consult `cancellation_requested()` SHALL therefore
stop on a terminal's behalf, not only on a `limit()`'s behalf.

`end()` SHALL still be awaited on the whole chain after an early stop, and the
terminal's `result()` SHALL be the result fixed before the stop.

#### Scenario: A matching terminal stops pulling from the source
- **WHEN** `any_match(predicate)` is called on a stream whose source has many elements and whose first element satisfies `predicate`
- **THEN** exactly one element is pulled from the source, and no further element is pulled

#### Scenario: A finding terminal stops pulling from the source
- **WHEN** `find_first()` or `find_any()` is called on a stream over a non-empty source
- **THEN** exactly one element is pulled from the source

#### Scenario: A short-circuiting terminal stops a flat_map mid-expansion
- **WHEN** a chain `.flat_map(mapper).any_match(predicate)` is consumed, and an element early in some outer element's expansion satisfies `predicate` while that inner stream still has elements left
- **THEN** the inner stream is not iterated past the satisfying element, and its generator is closed

#### Scenario: A non-short-circuiting terminal does not request cancellation
- **WHEN** `count()`, `reduce()`, `for_each()`, `max()` or `min()` is driven over a source
- **THEN** `cancellation_requested()` never reports `True` on their behalf and every source element is pulled

#### Scenario: end() and result() survive an early stop
- **WHEN** a chain containing a buffering intermediate operation is stopped early by a short-circuiting terminal
- **THEN** `end()` is awaited on every sink in the chain, and the terminal's returned result is the one fixed at the moment of the stop

#### Scenario: A short-circuiting terminal stops a buffering operation's flush
- **WHEN** a chain `.sorted().peek(fn).find_first()` is driven over an unsorted source
- **THEN** the terminal returns the smallest element, and `fn` is called exactly once — the sort's flush stops rather than pushing its whole buffer past the settled terminal

### Requirement: A parallel stream's terminal accumulates across all branches

When a terminal sink is driven under the racing executor, it SHALL receive every
element that the racing branches produce, exactly once each, and SHALL produce
the same result the same terminal produces under the sequential executor for any
order-independent operation.

A short-circuiting terminal under the racing executor SHALL stop consuming the
race once its result is fixed, and SHALL leave no in-flight branch task
uncancelled or its exception unretrieved.

Cancellation under the racing executor SHALL reach the loop consuming the race,
but NOT the sinks inside an in-flight branch: each branch holds its own sink
chain and the terminal is not a member of it. A branch's own `limit()` or
`flat_map()` therefore SHALL NOT be expected to stop on a terminal's behalf.

#### Scenario: A parallel terminal sees every element once
- **WHEN** `count()` or `reduce()` is called on a parallel stream over a source with many elements
- **THEN** the result reflects every source element exactly once, matching the sequential result

#### Scenario: A parallel short-circuiting terminal tears down cleanly
- **WHEN** `any_match(predicate)` is called on a parallel stream and an early element satisfies `predicate`
- **THEN** it returns `True` and no unhandled exception or warning escapes from the abandoned racing branches

### Requirement: Operations that need a generator use the executor's element-producing form

`iterator()`, `collect(to_generator)` and `Stream.concat()` SHALL obtain an
`AsyncGenerator` by composing the chain through the executor's
element-producing operation, which is backed by the generator bridge.

The single-`Collector` form of `collect()` — including `to_array()`'s
`collect(to_list())` — SHALL NOT use the bridge when the stream's executor
provides a fused drive: a `Collector` is driven through a terminal sink like
every other terminal operation, so its elements are pushed straight into the
accumulation container with nothing buffered on the way. `to_generator` remains
bridge-backed, since it is lazy and streaming.

`sequential()` and `parallel()` SHALL NOT compose the chain at all. A mode
switch returns a new stream carrying the same source and the same queued chain
under a different executor, so no generator is created and no chain is frozen at
the point of the switch.

Collectors SHALL be `Collector` values, not plain callables. The collector
interface SHALL remain independent of how a stream executes: the same
`Collector` collects a sequential and a parallel stream identically.

#### Scenario: iterator() returns an async generator
- **WHEN** `iterator()` is called on a stream with a chain of intermediate operations
- **THEN** it returns an `AsyncGenerator` yielding the elements that chain produces, in order

#### Scenario: A Collector is driven through a terminal sink
- **WHEN** `collect(collector)` is called with any `Collector` in the library
- **THEN** the chain is pushed into a terminal sink that supplies, accumulates and finishes, and the collected result is returned

#### Scenario: `to_generator` still composes through the bridge
- **WHEN** `collect(to_generator)` is called
- **THEN** the chain is composed to an `AsyncGenerator` through the bridge, and elements are yielded lazily as they are pulled

#### Scenario: Collectors are unaffected by terminal-sink execution
- **WHEN** the same `Collector` is used on a sequential and on a parallel stream over the same source
- **THEN** both produce the result that collector defines, subject only to the ordering guarantees the stream's mode already gives — the collector itself is written against supplier/accumulator/finisher and never against a drive mechanism

#### Scenario: A mode switch does not compose
- **WHEN** `sequential()` or `parallel()` is called mid-pipeline
- **THEN** the new stream carries the same source and the same queued chain as the receiver, with no generator composed at the point of the switch, and a terminal on the new stream applies every queued operation under the new executor
