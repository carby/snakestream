## MODIFIED Requirements

### Requirement: The concatenated stream is ordered only if both operands are

The stream returned by `Stream.concat(a, b)` SHALL carry the encounter-order
characteristic only when **both** `a` and `b` are ordered at the end of their
respective chains; if either operand is unordered, the concatenated stream SHALL
be unordered. This matches Java's `Stream.concat`, whose result "is ordered if
both of the input streams are ordered".

The characteristic SHALL NOT be stored as per-instance state on the concatenated
stream: the `pipeline-immutability` capability requires that the pipeline's
ordering characteristic not be carried alongside the chain, and the
`stream-ordering` capability defines it as a positional fold over the chain. An
unordered result is therefore expressed as an operation occupying a position in
the concatenated stream's chain — the same mechanism `unordered()` uses, applied
here by `concat()` on the caller's behalf.

An operation queued onto an unordered concatenated stream SHALL therefore see an
unordered pipeline, and under the fork-join executor SHALL NOT be charged the
reorder barrier that an ordered pipeline requires.

#### Scenario: Both operands ordered

- **WHEN** `Stream.concat(a, b)` is called with neither operand having had
  `unordered()` applied
- **THEN** the concatenated stream is ordered

#### Scenario: Either operand unordered

- **WHEN** `Stream.concat(a, b)` is called with `unordered()` applied to `a`
  only, and again with it applied to `b` only, and again with it applied to both
- **THEN** the concatenated stream is unordered in all three cases

#### Scenario: The unordered result is expressed positionally, not as state

- **WHEN** an unordered concatenated stream is extended by further intermediate
  operations
- **THEN** those operations see an unordered pipeline, and the characteristic is
  derived from the concatenated stream's chain rather than from a stored flag

#### Scenario: An order-sensitive operation on an unordered result takes no barrier

- **WHEN** an operation whose result depends on element position is queued onto
  an unordered concatenated stream that reports itself as parallel, and the
  pipeline is consumed
- **THEN** the operation runs without the encounter-order barrier an ordered
  racing pipeline would require of it
