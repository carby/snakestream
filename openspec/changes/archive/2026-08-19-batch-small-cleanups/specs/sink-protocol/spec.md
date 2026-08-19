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
