## ADDED Requirements

### Requirement: The concatenated stream's execution mode follows either operand

The stream returned by `Stream.concat(a, b)` SHALL report itself as parallel if
**either** `a` or `b` is parallel, and as sequential only when neither is. This
matches Java's `Stream.concat`, whose result "is parallel if either of the input
streams is parallel".

The mode so determined SHALL govern operations queued onto the concatenated
stream, exactly as a mode selected by `parallel()` would. It SHALL remain
overridable by a later `sequential()` or `parallel()` call on the concatenated
stream, which carries no special status here.

Each operand's own execution mode continues to govern that operand's own queued
operations, which is already the case and is unchanged: the requirement here
concerns only what the *result* carries forward.

#### Scenario: Both operands parallel

- **WHEN** `Stream.concat(a, b)` is called with both `a` and `b` parallel
- **THEN** the concatenated stream reports itself as parallel

#### Scenario: One operand parallel

- **WHEN** `Stream.concat(a, b)` is called with `a` parallel and `b` sequential,
  and again with `a` sequential and `b` parallel
- **THEN** the concatenated stream reports itself as parallel in both cases

#### Scenario: Neither operand parallel

- **WHEN** `Stream.concat(a, b)` is called with both operands sequential
- **THEN** the concatenated stream reports itself as sequential

#### Scenario: A later mode switch still governs

- **WHEN** a concatenated stream that reports itself as parallel has
  `sequential()` called on it
- **THEN** the resulting stream reports itself as sequential

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
unordered pipeline, and under the racing executor SHALL NOT be charged the
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

### Requirement: concat() invalidates both operands

`Stream.concat(a, b)` SHALL mark both `a` and `b` as extended, so that any
subsequent intermediate or terminal operation on either operand raises
`IllegalStateException`. This matches Java, where the operands of `concat` are
linked into the resulting pipeline and a later operation on one of them throws.

The invalidation SHALL take effect when `concat()` is called, not when the
concatenated stream is first consumed.

Without it, an operand remains live over a source the concatenated stream also
draws from, and draining the operand afterwards silently removes elements from
the concatenated stream's output rather than raising — a wrong answer in place
of an error.

#### Scenario: An operand cannot be terminally consumed after concat

- **WHEN** `Stream.concat(a, b)` is called and a terminal operation is then
  awaited on `a`
- **THEN** it raises `IllegalStateException`, rather than yielding elements

#### Scenario: An operand cannot be extended after concat

- **WHEN** `Stream.concat(a, b)` is called and an intermediate operation is then
  called on `b`
- **THEN** it raises `IllegalStateException`

#### Scenario: Invalidation fires at call time

- **WHEN** `Stream.concat(a, b)` is called and no element has been pulled from
  the concatenated stream
- **THEN** a subsequent operation on `a` already raises `IllegalStateException`

#### Scenario: The same operand cannot be concatenated twice

- **WHEN** `Stream.concat(a, b)` is called and `a` is then passed to a second
  `Stream.concat(a, c)`
- **THEN** the second call raises `IllegalStateException`

#### Scenario: The concatenated stream itself is unaffected

- **WHEN** `Stream.concat(a, b)` is called
- **THEN** the concatenated stream supports intermediate and terminal operations
  normally, and yields every element of `a` followed by every element of `b`

### Requirement: The concatenated stream is a base Stream

The stream returned by `Stream.concat(a, b)` SHALL be an instance of `Stream`
itself, and SHALL NOT adopt the concrete type of either operand, even when both
operands share a subclass.

This is a decision rather than an omission, and is stated so that a later reader
finds a reason rather than a silence. `a` and `b` may be instances of different
subclasses, so there is no principled choice between them; a subclass's
constructor may require arguments `concat()` has no way to supply; and Java
returns an internal stream type from `concat` for the same reason. Callers
needing subclass behaviour on a concatenation should construct their subclass
over the concatenated stream rather than expecting `concat()` to infer it.

#### Scenario: Concatenating two subclass instances yields a base Stream

- **WHEN** `Stream.concat(a, b)` is called where `a` and `b` are instances of the
  same `Stream` subclass
- **THEN** the result's concrete type is `Stream`, not that subclass

#### Scenario: Concatenating instances of different subclasses does not raise

- **WHEN** `Stream.concat(a, b)` is called where `a` and `b` are instances of two
  different `Stream` subclasses
- **THEN** the call succeeds and returns a base `Stream`
