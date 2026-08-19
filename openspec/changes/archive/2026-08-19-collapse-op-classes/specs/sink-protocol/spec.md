## MODIFIED Requirements

### Requirement: Shared state is delivered through begin

`begin()` SHALL take a single state map argument and propagate that same
argument unchanged to `downstream.begin()`. A sink requiring state SHALL look
up its own originating operation in that map and use the entry found there; if
its operation has no entry, the sink SHALL initialize fresh state local to
itself.

Operations requiring shared state SHALL expose a factory for creating one
instance of that state, so a caller can build a state map without inspecting
sink internals.

That factory SHALL be the only statement of what an operation's state is: a
sink falling back to fresh local state SHALL obtain it from its originating
operation's factory rather than constructing state of its own. Shared state and
local fallback state are therefore always the same shape, and an operation's
state shape cannot drift between the two.

#### Scenario: A stateful sink uses the state supplied in the map
- **WHEN** a state map containing an entry for a stateful sink's originating operation is passed to `begin()`
- **THEN** that sink uses the supplied state instance rather than creating its own

#### Scenario: A stateful sink falls back to fresh local state
- **WHEN** a state map with no entry for a stateful sink's originating operation is passed to `begin()`
- **THEN** that sink initializes fresh state local to itself

#### Scenario: Fallback state comes from the operation's own factory
- **WHEN** a stateful sink begins with a state map that has no entry for its operation
- **THEN** the state it uses is one produced by that operation's state factory, indistinguishable in shape from the state the same operation would have contributed to a state map

#### Scenario: Two sinks built from one operation share one state instance
- **WHEN** two separate sink chains are built from the same list of operations and both are given the same state map at `begin()`
- **THEN** the two sinks built from a given stateful operation observe and mutate the same state instance
