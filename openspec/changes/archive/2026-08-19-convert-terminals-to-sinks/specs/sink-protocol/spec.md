## MODIFIED Requirements

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
