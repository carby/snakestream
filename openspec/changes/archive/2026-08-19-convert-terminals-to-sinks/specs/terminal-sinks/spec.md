## Purpose

Defines how a stream's terminal operations execute: as terminal sinks fed by the same push protocol the intermediate operations use, driven by a loop that pushes source elements through the chain and returns the terminal's finished result — rather than pulling elements out of a composed `AsyncGenerator`. Covers what a short-circuiting terminal is entitled to do (request cancellation so upstream operations stop), which terminals still go through a generator, and the ordered-drive variant that `for_each_ordered()` and an ordered `ParallelStream.find_first()` rely on.

## ADDED Requirements

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
have produced. Each of these operations SHALL keep its existing signature,
return type, and returned value for every input.

An element pushed to a terminal SHALL NOT be buffered into an intermediate
container and re-pulled on its way there: the chain's last intermediate sink
SHALL push directly into the terminal sink.

#### Scenario: A terminal returns the same result as before the conversion
- **WHEN** any of the listed terminal operations is called on a stream with any chain of intermediate operations
- **THEN** it returns the same value it returned when it consumed the composed generator, for the same source and the same chain

#### Scenario: A terminal over an empty source returns its empty result
- **WHEN** any of the listed terminal operations is called on a stream whose source yields no elements
- **THEN** it returns that operation's documented empty-source result (for example `0` from `count()`, `None` from `find_any()`, `True` from `all_match()`) without error

#### Scenario: An async user callable in a terminal is awaited
- **WHEN** a terminal operation is given an async consumer, predicate, comparator or accumulator
- **THEN** that callable is awaited per element, with the same sync-or-async dispatch behavior every other user-supplied callable in the library has

#### Scenario: Terminals still reject an already-consumed stream
- **WHEN** a terminal operation is called on a stream reference that has already been extended into a new instance
- **THEN** it raises `IllegalStateException`, unchanged from before the conversion

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

### Requirement: Operations that need a generator keep using the bridge

`iterator()`, `collect(collector)` (the single-collector form, including
`to_array()`), `Stream.concat()`, and the `sequential()` / `parallel()` mode
handoff SHALL continue to obtain an `AsyncGenerator` from composing the chain
through the generator bridge, unchanged.

Collectors SHALL continue to be plain callables taking a composed
`AsyncGenerator`. This change SHALL NOT alter the collector interface.

#### Scenario: iterator() still returns an async generator
- **WHEN** `iterator()` is called on a stream with a chain of intermediate operations
- **THEN** it returns an `AsyncGenerator` yielding the same elements in the same order as before

#### Scenario: Collectors are unaffected
- **WHEN** `collect(collector)` is called with any collector in the library
- **THEN** the collector receives a composed `AsyncGenerator` and returns the same result as before

#### Scenario: A mode switch still composes to a generator
- **WHEN** `sequential()` or `parallel()` is called mid-pipeline
- **THEN** the new stream's source is a composed generator over the previous chain, and the resulting pipeline produces the same elements as before

### Requirement: An ordered drive is available regardless of stream mode

A terminal SHALL be able to request a strictly ordered, single-flight push
through the chain, bypassing any racing execution the stream's mode would
otherwise use. `for_each_ordered()` SHALL use it, and `ParallelStream`'s
`find_first()` SHALL use it whenever the stream is ordered.

The ordered drive SHALL deliver elements to the terminal in source encounter
order for both `Stream` and `ParallelStream`.

#### Scenario: for_each_ordered() stays in source order on a parallel stream
- **WHEN** `for_each_ordered(consumer)` is called on a `ParallelStream` whose chain reorders arrival timing (for example a `map()` with a positional delay)
- **THEN** `consumer` is invoked with the elements in source encounter order

#### Scenario: An ordered parallel find_first() returns the true first element
- **WHEN** `find_first()` is called on an ordered `ParallelStream` whose chain reorders arrival timing
- **THEN** it returns the first element in source encounter order, not the first to arrive

#### Scenario: An unordered parallel find_first() still races
- **WHEN** `find_first()` is called on a `ParallelStream` that has been marked `unordered()`
- **THEN** it behaves as `find_any()` does, returning the first element to arrive

### Requirement: A parallel stream's terminal accumulates across all branches

When a terminal sink is driven on a `ParallelStream`, it SHALL receive every
element that the racing branches produce, exactly once each, and SHALL produce
the same result the same terminal produces on the equivalent sequential
stream for any order-independent operation.

A short-circuiting terminal on a `ParallelStream` SHALL stop consuming the race
once its result is fixed, and SHALL leave no in-flight branch task uncancelled
or its exception unretrieved.

#### Scenario: A parallel terminal sees every element once
- **WHEN** `count()` or `reduce()` is called on a `ParallelStream` over a source with many elements
- **THEN** the result reflects every source element exactly once, matching the sequential result

#### Scenario: A parallel short-circuiting terminal tears down cleanly
- **WHEN** `any_match(predicate)` is called on a `ParallelStream` and an early element satisfies `predicate`
- **THEN** it returns `True` and no unhandled exception or warning escapes from the abandoned racing branches
