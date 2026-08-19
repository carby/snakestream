## Purpose

Defines the `Sink` protocol that intermediate and terminal operations use to build a pushed pipeline: an async `begin(state_map)` / `accept(element)` / `end()` interface, plus a synchronous `cancellation_requested()` query for short-circuiting ops. Intermediate sinks chain by holding a `downstream` sink and pushing results to it via `accept()`; a terminal sink has no `downstream` and instead accumulates into its own container, exposing the finished value via `result()`. Composing a stream still returns an `AsyncGenerator`, via a bridge sink that occupies the terminal seat and converts pushed elements back into yields.

## Requirements

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

The loop SHALL also query `cancellation_requested()` on the head sink once
after `begin()` and before its **first** pull, and SHALL pull nothing at all
when it already reports `True`. A chain can be cancelled before it has seen any
element — a limiting op capped at zero is cancelled from the moment it begins —
and without this query the loop would pull, and push through every upstream
operation, one element whose result is discarded.

A sink that pushes more than one element downstream without returning to the
driving loop — a buffering sink flushing from `end()`, or a flattening sink
expanding one accepted element — SHALL query `downstream.cancellation_requested()`
between those pushes and SHALL stop pushing once it reports `True`. The driving
loop cannot observe cancellation during such a burst, so this is the only point
at which it can be honoured.

A sink whose result is already settled SHALL NOT be corrupted by an element
pushed to it after it requested cancellation: it SHALL either be guaranteed no
such push (by the rule above) or ignore what arrives. A short-circuiting sink
SHALL therefore keep the value it settled on.

#### Scenario: Cancellation from a mid-chain sink is visible at the head
- **WHEN** a limiting sink in the middle of a chain has accepted its maximum number of elements
- **THEN** `cancellation_requested()` on the head sink reports `True`

#### Scenario: The driving loop stops pulling once cancellation is requested
- **WHEN** a chain containing a limiting sink capped at `n` is driven over a source with more than `n` elements
- **THEN** exactly `n` elements are pulled from the source, and no `(n+1)`th pull occurs

#### Scenario: A loop that begins already cancelled pulls nothing
- **WHEN** a chain whose head sink reports `cancellation_requested()` as `True` immediately after `begin()` is driven over a non-empty source
- **THEN** no element is pulled from the source at all, and no upstream sink's `accept()` is invoked

#### Scenario: end() still runs after cancellation
- **WHEN** a driving loop stops early because `cancellation_requested()` reported `True`
- **THEN** `end()` is still awaited on the head sink, and propagates through the whole chain

#### Scenario: A buffering sink stops flushing when downstream cancels
- **WHEN** a sorting sink flushes its buffer from `end()` and the downstream sink requests cancellation partway through the flush
- **THEN** the sorting sink stops pushing, and no downstream sink observes an element after the one that triggered cancellation

#### Scenario: A settled short-circuiting sink keeps its value
- **WHEN** a sink that has already requested cancellation is nevertheless given another element
- **THEN** its result is unchanged from the value it settled on, and any user callable it holds is not invoked again

### Requirement: Terminal sink produces a result

A terminal sink SHALL create its accumulation container during `begin()`,
accumulate accepted elements into it during `accept()`, finish it during
`end()`, and expose the finished value via `result()`. `result()` SHALL only be
called after `end()` has been awaited.

A terminal sink whose result becomes fixed before the source is exhausted SHALL
be permitted to report `cancellation_requested()` as `True` from that point on,
exactly as a short-circuiting intermediate sink may. Because the terminal sits
at the end of the chain, that report SHALL propagate up through every
intermediate sink's `cancellation_requested()` to the head, and the driving
loop SHALL stop pulling from the source on it. A terminal sink that reports
cancellation SHALL still receive `end()`, and its `result()` SHALL be the
result that was fixed at the point of cancellation.

A driving loop MAY drive a chain onto a terminal sink and return
`terminal.result()` directly, instead of surfacing elements as yields. In that
form no element is buffered on its way to the terminal: the chain's last
intermediate sink pushes straight into the terminal sink.

This shape is the seat a future `Collector(supplier, accumulator, combiner,
finisher)` occupies: `begin` corresponds to `supplier`, `accept` to
`accumulator`, and `end`/`result` to `finisher`.

#### Scenario: A terminal sink yields its accumulated result after end
- **WHEN** a terminal sink is driven over a source and `end()` is awaited
- **THEN** `result()` returns the value accumulated from every accepted element

#### Scenario: A terminal sink over an empty source returns its empty container
- **WHEN** a terminal sink is driven over a source with zero elements and `end()` is awaited
- **THEN** `result()` returns the empty container produced by `begin()`, not an error

#### Scenario: A short-circuiting terminal sink is visible at the head
- **WHEN** a terminal sink at the end of a chain of intermediate sinks reports `cancellation_requested()` as `True`
- **THEN** `cancellation_requested()` on the head sink also reports `True`

#### Scenario: A cancelling terminal sink still finishes
- **WHEN** a driving loop stops early because the terminal sink requested cancellation
- **THEN** `end()` is awaited on the whole chain, and `result()` returns the value fixed before the stop

#### Scenario: Driving to a terminal returns the result without yielding
- **WHEN** a chain is driven onto a terminal sink by a loop that returns `result()` rather than yielding
- **THEN** the returned value equals what accumulating the same elements through the same terminal sink produces, and no intermediate buffer holds the elements on the way

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
