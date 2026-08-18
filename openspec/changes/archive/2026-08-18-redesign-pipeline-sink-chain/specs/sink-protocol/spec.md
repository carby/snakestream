## ADDED Requirements

### Requirement: Sink protocol shape

A `Sink` SHALL expose four members: `async begin(state_map)`,
`async accept(element)`, `async end()`, and `cancellation_requested()`.
`begin()`, `accept()` and `end()` SHALL be awaitable; `cancellation_requested()`
SHALL be a plain synchronous query returning `bool`.

An **intermediate** sink SHALL hold a reference to exactly one `downstream`
sink and SHALL push results to it by awaiting `downstream.accept(...)`. A
**terminal** sink SHALL have no `downstream`.

#### Scenario: An intermediate sink pushes to its downstream
- **WHEN** an intermediate sink's `accept(element)` produces a result for that element
- **THEN** it awaits `downstream.accept(result)` rather than yielding the result

#### Scenario: A terminal sink has no downstream
- **WHEN** a terminal sink is constructed
- **THEN** it has no `downstream` reference and its `accept()` accumulates into its own container instead of pushing further

### Requirement: Lifecycle call ordering

For any sink chain, `begin()` SHALL be awaited on the head sink exactly once
before the first `accept()`, and `end()` SHALL be awaited on the head sink
exactly once after the last `accept()`. No `accept()` SHALL be awaited after
`end()` has been awaited.

`begin()` and `end()` SHALL each propagate down the chain: an intermediate
sink's `begin()` SHALL await `downstream.begin()` and its `end()` SHALL await
`downstream.end()`, so that every sink in the chain receives exactly one
`begin()` and exactly one `end()`.

#### Scenario: Every sink in the chain receives begin and end exactly once
- **WHEN** a chain of three intermediate sinks onto a terminal sink is driven to completion
- **THEN** each of the four sinks has had `begin()` awaited exactly once and `end()` awaited exactly once

#### Scenario: begin precedes every accept and end follows every accept
- **WHEN** a sink chain is driven over a source with one or more elements
- **THEN** every sink observes its `begin()` before its first `accept()`, and its `end()` after its last `accept()`

#### Scenario: end still runs on an empty source
- **WHEN** a sink chain is driven over a source with zero elements
- **THEN** `begin()` and `end()` are still each awaited exactly once on every sink, with no `accept()` in between

### Requirement: A sink may push zero, one, or many elements per accept

A single `accept(element)` on an intermediate sink SHALL be permitted to await
`downstream.accept(...)` zero times (a filtering op rejecting the element),
exactly once (a one-to-one mapping op), or many times (a flattening op). An
intermediate sink SHALL also be permitted to push elements from `end()` rather
than from `accept()`, for ops that must observe the whole stream before
emitting anything.

#### Scenario: A filtering sink pushes nothing for a rejected element
- **WHEN** a filtering sink's predicate rejects the accepted element
- **THEN** `downstream.accept()` is not awaited for that element

#### Scenario: A flattening sink pushes many elements for one accepted element
- **WHEN** a flattening sink accepts one element that expands into several
- **THEN** it awaits `downstream.accept()` once per expanded element, in order

#### Scenario: A buffering sink pushes from end()
- **WHEN** a sink that must see the whole stream (e.g. a sorting sink) is driven
- **THEN** it pushes no elements from `accept()` and pushes all of its elements downstream from `end()`, before awaiting `downstream.end()`

### Requirement: Shared state is delivered through begin

`begin()` SHALL take a single state map argument and propagate that same
argument unchanged to `downstream.begin()`. A sink requiring state SHALL look
up its own originating operation in that map and use the entry found there; if
its operation has no entry, the sink SHALL initialize fresh state local to
itself.

Operations requiring shared state SHALL expose a factory for creating one
instance of that state, so a caller can build a state map without inspecting
sink internals.

#### Scenario: A stateful sink uses the state supplied in the map
- **WHEN** a state map containing an entry for a stateful sink's originating operation is passed to `begin()`
- **THEN** that sink uses the supplied state instance rather than creating its own

#### Scenario: A stateful sink falls back to fresh local state
- **WHEN** a state map with no entry for a stateful sink's originating operation is passed to `begin()`
- **THEN** that sink initializes fresh state local to itself

#### Scenario: Two sinks built from one operation share one state instance
- **WHEN** two separate sink chains are built from the same list of operations and both are given the same state map at `begin()`
- **THEN** the two sinks built from a given stateful operation observe and mutate the same state instance

### Requirement: Cancellation propagates upward and stops the driving loop

`cancellation_requested()` SHALL report `True` once a downstream sink has
determined it will accept no further elements. An intermediate sink SHALL
report `True` if its own downstream reports `True`, so that a query on the head
sink reflects the state of the whole chain. A sink that itself decides no
further elements are wanted (e.g. a short-circuiting limiting op) SHALL report
`True` from that point on regardless of its downstream.

The loop driving a sink chain SHALL query `cancellation_requested()` on the
head sink after each `accept()` and SHALL stop pulling from the source when it
reports `True`.

#### Scenario: Cancellation from a mid-chain sink is visible at the head
- **WHEN** a limiting sink in the middle of a chain has accepted its maximum number of elements
- **THEN** `cancellation_requested()` on the head sink reports `True`

#### Scenario: The driving loop stops pulling once cancellation is requested
- **WHEN** a chain containing a limiting sink capped at `n` is driven over a source with more than `n` elements
- **THEN** exactly `n` elements are pulled from the source, and no `(n+1)`th pull occurs

#### Scenario: end() still runs after cancellation
- **WHEN** a driving loop stops early because `cancellation_requested()` reported `True`
- **THEN** `end()` is still awaited on the head sink, and propagates through the whole chain

### Requirement: Terminal sink produces a result

A terminal sink SHALL create its accumulation container during `begin()`,
accumulate accepted elements into it during `accept()`, finish it during
`end()`, and expose the finished value via `result()`. `result()` SHALL only be
called after `end()` has been awaited.

This shape is the seat a future `Collector(supplier, accumulator, combiner,
finisher)` occupies: `begin` corresponds to `supplier`, `accept` to
`accumulator`, and `end`/`result` to `finisher`.

#### Scenario: A terminal sink yields its accumulated result after end
- **WHEN** a terminal sink is driven over a source and `end()` is awaited
- **THEN** `result()` returns the value accumulated from every accepted element

#### Scenario: A terminal sink over an empty source returns its empty container
- **WHEN** a terminal sink is driven over a source with zero elements and `end()` is awaited
- **THEN** `result()` returns the empty container produced by `begin()`, not an error

### Requirement: The generator bridge exposes a pushed chain as an async generator

Composing a stream SHALL drive the sink chain internally while still returning
an `AsyncGenerator`. The bridge SHALL occupy the terminal seat, buffering the
elements pushed to it and surfacing them as yields, such that the elements
yielded and their order are identical to what an equivalent pull-based chain
would have produced.

The bridge SHALL yield the elements produced by an `accept()` after that
`accept()` returns, and SHALL yield any elements produced during `end()` after
`end()` returns. The source SHALL be closed when the driving loop exits,
including when it exits early due to cancellation.

#### Scenario: Bridged output matches pull-based output
- **WHEN** a chain of intermediate operations is composed and fully consumed via the bridge
- **THEN** the sequence of yielded elements is identical to the sequence the same chain produced before the push-based redesign

#### Scenario: Elements produced during end() are yielded
- **WHEN** a chain containing a sorting operation is composed and consumed via the bridge
- **THEN** every element pushed downstream during `end()` is yielded before the generator terminates

#### Scenario: The source is closed on early termination
- **WHEN** a composed chain is abandoned before exhaustion, or terminates early because cancellation was requested
- **THEN** the underlying source generator is closed
