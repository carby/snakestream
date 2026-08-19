## ADDED Requirements

### Requirement: Operation protocol shape

Every intermediate operation held in a stream's chain SHALL be an `Op`: an
object exposing `link(downstream)`, which builds and returns the `Sink` that
does that operation's per-element work and pushes to `downstream`; and
`make_shared_state()`, which returns one fresh instance of the state that
operation's sinks share, or `None` if the operation is stateless.

`link()` SHALL be a plain synchronous call returning a `Sink`, and SHALL be
callable more than once on the same operation, returning an independent sink
each time. `make_shared_state()` SHALL default to returning `None`, so a
stateless operation implements only `link()`.

`None` SHALL be reserved as the "no shared state" answer: an operation that
needs shared state SHALL return a container (a set, a list, a counter object),
never `None`.

#### Scenario: An operation builds its sink

- **WHEN** `link(downstream)` is called on an operation with a downstream sink
- **THEN** it returns a sink whose `accept()` performs that operation and pushes results to the given downstream

#### Scenario: One operation builds independent sinks

- **WHEN** `link()` is called twice on the same operation, with two different downstream sinks
- **THEN** two separate sink instances are returned, each holding its own downstream

#### Scenario: A stateless operation reports no shared state

- **WHEN** `make_shared_state()` is called on an operation that declares no state of its own
- **THEN** it returns `None`

#### Scenario: A stateful operation reports a fresh container

- **WHEN** `make_shared_state()` is called twice on a stateful operation
- **THEN** each call returns a new, empty state container, and the two are not the same object

### Requirement: Shared state is collected without probing operations

A caller building a state map for a chain SHALL call `make_shared_state()` on
every operation in that chain unconditionally, and SHALL record an entry keyed
by the operation only when the returned state is not `None`. A caller SHALL NOT
test for the presence of the method before calling it.

#### Scenario: A chain of mixed stateful and stateless operations yields entries only for the stateful ones

- **WHEN** a state map is built for a chain containing both stateful and stateless operations
- **THEN** the map contains one entry per stateful operation, keyed by that operation, and no entry for any stateless operation

#### Scenario: A stateless operation's sink still begins successfully

- **WHEN** a sink built from a stateless operation receives `begin(state_map)` with a map that has no entry for its operation
- **THEN** it begins normally and propagates `begin()` downstream, with no lookup failure
