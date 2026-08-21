## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: An ordered drive is available regardless of stream mode

A terminal SHALL be able to request a strictly ordered, single-flight push
through the chain, bypassing any racing execution the stream's executor would
otherwise use. It SHALL do so by naming the sequential executor explicitly.
`for_each_ordered()` SHALL use it unconditionally, and `find_first()` SHALL use
it whenever the stream is ordered.

The ordered drive SHALL deliver elements to the terminal in source encounter
order whichever executor the stream carries.

#### Scenario: for_each_ordered() stays in source order on a parallel stream
- **WHEN** `for_each_ordered(consumer)` is called on a parallel stream whose chain reorders arrival timing (for example a `map()` with a positional delay)
- **THEN** `consumer` is invoked with the elements in source encounter order

#### Scenario: An ordered parallel find_first() returns the true first element
- **WHEN** `find_first()` is called on an ordered parallel stream whose chain reorders arrival timing
- **THEN** it returns the first element in source encounter order, not the first to arrive

#### Scenario: An unordered parallel find_first() still races
- **WHEN** `find_first()` is called on a parallel stream that has been marked `unordered()`
- **THEN** it behaves as `find_any()` does, returning the first element to arrive

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

## REMOVED Requirements

### Requirement: Operations that need a generator keep using the bridge
**Reason**: Restructured rather than dropped. Its "`sequential()`/`parallel()`
mode handoff obtains an `AsyncGenerator`" clause, and the scenario asserting
that a mode switch composes the previous chain into the new stream's source,
both describe the compose-and-handoff that this change removes — a mode switch
now carries the chain rather than freezing it. The replacement requirement above
restates every other guarantee verbatim and corrects that one.
**Migration**: None for callers of `iterator()`, `collect(to_generator)` or
`Stream.concat()`, whose behaviour is unchanged. Callers relying on a mode
switch freezing the ops declared before it — see the `pipeline-composition` and
`stream-execution-model` deltas — are covered by this change's migration note.
