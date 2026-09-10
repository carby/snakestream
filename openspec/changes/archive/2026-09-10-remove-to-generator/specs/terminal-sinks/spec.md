## REMOVED Requirements

### Requirement: Operations that need a generator use the executor's element-producing form

**Reason**: Replaced by the requirement of the same shape below, renamed because
its subject list shrank: `collect(to_generator)` was one of the three operations
it named, and it is gone. The old requirement also carried a scenario asserting
`to_generator` still composes through the bridge, which has nothing left to
assert.

**Migration**: None for a caller — `iterator()` and `Stream.concat()` behave
exactly as before. A caller who reached the bridge through
`collect(to_generator)` reaches it through `iterator()`.

## ADDED Requirements

### Requirement: `iterator()` and `concat()` use the executor's element-producing form

`iterator()` and `Stream.concat()` SHALL obtain an `AsyncGenerator` by
composing the chain through the executor's element-producing operation, which
is backed by the generator bridge. These are the only two operations that do:
no form of `collect()` composes through the bridge.

The single-`Collector` form of `collect()` — including `to_array()`'s
`collect(to_list())` — SHALL NOT use the bridge when the stream's executor
provides a fused drive: a `Collector` is driven through a terminal sink like
every other terminal operation, so its elements are pushed straight into the
accumulation container with nothing buffered on the way. This SHALL hold for
every single-argument `collect()` without exception — there is no
bridge-backed collector.

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

#### Scenario: Collectors are unaffected by terminal-sink execution
- **WHEN** the same `Collector` is used on a sequential and on a parallel stream over the same source
- **THEN** both produce the result that collector defines, subject only to the ordering guarantees the stream's mode already gives — the collector itself is written against supplier/accumulator/finisher and never against a drive mechanism

#### Scenario: A mode switch does not compose
- **WHEN** `sequential()` or `parallel()` is called mid-pipeline
- **THEN** the new stream carries the same source and the same queued chain as the receiver, with no generator composed at the point of the switch, and a terminal on the new stream applies every queued operation under the new executor

#### Scenario: No collector composes through the bridge
- **WHEN** any value `collect()` accepts in its single-argument form is passed to it on a stream whose executor provides a fused drive
- **THEN** the chain is driven into a terminal sink, and no bridge-backed generator is composed for it
