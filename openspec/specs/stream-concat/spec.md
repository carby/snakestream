## Purpose

Defines `Stream.concat(a, b)` — how it is called (a plain static factory, not
a coroutine function) and what the concatenated stream it returns contains:
every element of the first stream, in order, followed by every element of the
second, pulled lazily from each side's own pipeline.

## Requirements

### Requirement: Stream.concat() is a plain static factory

`Stream.concat(a, b)` SHALL be an ordinary (non-`async`) static method that
returns a `Stream` directly. Its result SHALL NOT be awaitable, and calling it
SHALL NOT require the caller to be inside a coroutine.

This matches every other static factory on `Stream` (`of()`, `empty()`,
`builder()`, `iterate()`) and Java's static `Stream.concat`.

#### Scenario: Concatenating without await

- **WHEN** `Stream.concat(a, b)` is called
- **THEN** it returns a `Stream` value directly, on which intermediate and
  terminal operations can be chained without an intervening `await`

#### Scenario: Awaiting the result is an error

- **WHEN** a caller writes `await Stream.concat(a, b)`
- **THEN** a `TypeError` is raised, because a `Stream` is not awaitable

#### Scenario: Callable outside a coroutine

- **WHEN** `Stream.concat(a, b)` is called from ordinary synchronous code
- **THEN** the concatenated `Stream` is constructed and returned, with no
  event loop required until a terminal operation is awaited

### Requirement: Concatenated contents and ordering

The stream returned by `Stream.concat(a, b)` SHALL yield every element of `a`,
in `a`'s order, followed by every element of `b`, in `b`'s order. Each input
stream's queued intermediate operations SHALL be applied to its own elements
before they reach the concatenated stream.

#### Scenario: Two plain sources

- **WHEN** `Stream.concat(a, b)` is consumed, where `a` yields `1, 2, 3, 4` and
  `b` yields `5, 6, 7`
- **THEN** the elements produced are exactly `1, 2, 3, 4, 5, 6, 7`, in that
  order, and the stream is then exhausted

#### Scenario: Inputs carrying intermediate operations

- **WHEN** `Stream.concat(a, b)` is consumed, where `a` is
  `Stream.of([1, 2, 3, 4]).filter(lambda x: x < 3)` and `b` is
  `Stream.of([5, 6, 7, 7]).distinct()`
- **THEN** the elements produced are exactly `1, 2, 5, 6, 7`, in that order

#### Scenario: Empty input on either side

- **WHEN** `Stream.concat(a, b)` is consumed and one of `a` or `b` yields no
  elements
- **THEN** the elements produced are exactly those of the other stream, in
  order

### Requirement: Concatenation is lazy

Constructing a concatenated stream SHALL NOT pull any element from `a` or `b`.
Elements SHALL be pulled from `a` only as the concatenated stream is consumed,
and from `b` only once `a` is exhausted.

#### Scenario: No work at construction time

- **WHEN** `Stream.concat(a, b)` is called but the result is never consumed
- **THEN** no element is pulled from either `a` or `b`, and no side effect
  queued on either pipeline (e.g. via `peek`) is observed

#### Scenario: Second stream untouched while the first is being consumed

- **WHEN** a concatenated stream is consumed only far enough to produce the
  first stream's elements
- **THEN** no element has been pulled from the second stream

### Requirement: The concatenated stream carries both operands' close handlers

The stream returned by `Stream.concat(a, b)` SHALL be constructed with the
close handlers registered on `a`, in their registration order, followed by
those registered on `b`, in their registration order. Calling `close()` on the
concatenated stream SHALL therefore invoke every handler registered on either
input, matching Java's `Stream.concat`, whose result closes both inputs.

Handlers SHALL be taken as they stand when `concat()` is called. Registering a
handler on `a` or `b` after `concat()` has returned SHALL NOT retroactively add
it to the concatenated stream, consistent with the concatenated stream being an
ordinary `Stream` constructed with an explicit `close_handlers` list per the
`stream-close-handling` capability.

The existing rules of that capability apply unchanged to the concatenated
stream: every handler runs, in order; a raising handler does not prevent later
handlers from running; and the first exception raised is the one propagated.

#### Scenario: Handlers from both inputs run

- **WHEN** `close()` is called on `Stream.concat(a, b)`, where `a` has close
  handler `handler_a` registered and `b` has `handler_b`
- **THEN** both `handler_a` and `handler_b` are invoked exactly once

#### Scenario: Handler order follows a then b

- **WHEN** `close()` is called on `Stream.concat(a, b)`, where `a` has handlers
  `[a1, a2]` and `b` has handlers `[b1, b2]`
- **THEN** the handlers are invoked in the order `a1, a2, b1, b2`

#### Scenario: One input has no handlers

- **WHEN** `close()` is called on `Stream.concat(a, b)`, where only `b` has a
  close handler registered
- **THEN** `b`'s handler is invoked and no error is raised

#### Scenario: Neither input has handlers

- **WHEN** `close()` is called on `Stream.concat(a, b)`, where neither input
  has a close handler registered
- **THEN** nothing is invoked and no error is raised

#### Scenario: Registering after concat does not affect the result

- **WHEN** `Stream.concat(a, b)` is called and a close handler is then
  registered on `a`, after which the concatenated stream's `close()` is called
- **THEN** the handler registered after `concat()` is not invoked

#### Scenario: A raising handler on one input does not skip the other's

- **WHEN** `close()` is called on `Stream.concat(a, b)`, where `a`'s handler
  raises and `b`'s does not
- **THEN** `b`'s handler is still invoked, and `a`'s exception is raised after
  both have run

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
