## MODIFIED Requirements

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

This shape is the seat a `Collector(supplier, accumulator, combiner,
finisher)` occupies: `begin` corresponds to `supplier`, `accept` to
`accumulator`, and `end`/`result` to `finisher`. `combiner` occupies the
partition protocol added below.

A terminal sink SHALL additionally expose a partition protocol: a synchronous
`can_partition()` reporting whether it supports being split into peer
accumulations, and two members meaningful only where it does -
`new_partition()`, returning a fresh peer sink configured the same way as the
sink it was called on, and `async merge_from(peer)`, folding a peer's
accumulated container into this sink's own, in place.

`can_partition()` SHALL default to `False`, so a terminal sink that declares
neither of the other two members behaves exactly as it did before this
protocol existed. Where a terminal declares `can_partition()` True,
`new_partition()` SHALL return an independent sink - calling it twice SHALL
return two sinks whose containers do not alias - and `merge_from(peer)` SHALL
be called only after `peer` has been driven through `begin()` and one or more
`accept()`s, and never after `peer.end()`: a peer is merged as an
accumulation, not a finished result, so `end()` (and the `finisher` it may
run) applies once, to the terminal that survives every merge, not to each
peer. `merge_from()` SHALL be called at most once per peer, and the caller
SHALL NOT invoke it concurrently on the same sink - an implementation depends
on running as a plain, unlocked left fold.

The specific rule a merge follows - batch order, and what a caller's combiner
and identity must satisfy for it to agree with the unpartitioned result - is
the `parallel-reduction` capability's, not this one's: this requirement states
only the shape of the protocol, which every terminal sink shares whether or
not it partitions.

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

#### Scenario: A terminal sink declines partitioning by default
- **WHEN** `can_partition()` is called on a terminal sink that does not override the partition protocol
- **THEN** it returns `False`, and neither `new_partition()` nor `merge_from()` is ever called on it

#### Scenario: A partitioning terminal's peers are independent
- **WHEN** `new_partition()` is called twice on a terminal sink that declares `can_partition()` True
- **THEN** the two returned sinks accumulate into containers that do not alias each other or the sink `new_partition()` was called on

#### Scenario: A peer is merged as a container, not a finished result
- **WHEN** a peer sink is driven through `begin()` and one or more `accept()`s and then merged with `merge_from()`
- **THEN** `end()` was never awaited on that peer, and the value folded into the merging sink is the peer's accumulated container
