## MODIFIED Requirements

### Requirement: Operations that need a generator keep using the bridge

`iterator()`, `collect(to_generator)`, `Stream.concat()`, and the
`sequential()` / `parallel()` mode handoff SHALL obtain an `AsyncGenerator` by
composing the chain through the generator bridge.

The single-`Collector` form of `collect()` — including `to_array()`'s
`collect(to_list)` — SHALL NOT use the bridge: a `Collector` is driven through
a terminal sink like every other terminal operation, so its elements are
pushed straight into the accumulation container with nothing buffered on the
way. `to_generator` remains bridge-backed, since it is lazy and streaming.

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

#### Scenario: A mode switch composes to a generator
- **WHEN** `sequential()` or `parallel()` is called mid-pipeline
- **THEN** the new stream's source is a composed generator over the previous chain, and the resulting pipeline produces the same elements the unswitched chain would
