## Purpose

Defines which of Python's data-model protocols `Stream` implements, which it
deliberately refuses, and why each refusal is a decision rather than a gap.
Most of the set follows from the library being async-first: a protocol that
demands a value synchronously cannot be satisfied by a type whose every
terminal operation is a coroutine, so the interesting content here is the
boundary — the protocols Python offers in an async or lazy form, which `Stream`
satisfies as a matter of parity with what Java's stream offers its own
language, and the two synchronous protocols whose silent defaults are wrong and
must be closed rather than left.

## ADDED Requirements

### Requirement: Stream is asynchronously iterable

`Stream` SHALL implement `__aiter__`, so that `async for element in stream` is
supported directly and is equivalent to `async for element in stream.iterator()`.

`__aiter__` SHALL delegate to `iterator()` rather than reimplement it, and SHALL
therefore inherit that capability's contract in full: composition of the queued
chain without pulling any element, the caller driving iteration, the
non-destructive composition that leaves the stream instance usable afterwards,
and the declaration that the order elements arrive in is observable — so an
ordered stream under the racing executor yields in encounter order through
`async for` exactly as it does through `iterator()`.

No requirement of the `stream-iterator` capability is altered by this. The two
entry points SHALL be indistinguishable in behaviour.

#### Scenario: Iterating a stream directly

- **WHEN** `async for element in stream` is written over a `Stream` with a queued
  chain of intermediate operations
- **THEN** it yields the same elements, in the same order, as
  `async for element in stream.iterator()` over an equivalent stream

#### Scenario: Direct iteration pulls nothing until driven

- **WHEN** `__aiter__` is invoked on a stream but no element is requested from
  the returned iterator
- **THEN** no element has been pulled from the underlying source, and no side
  effect queued on the pipeline has been observed

#### Scenario: An ordered racing stream iterates in encounter order

- **WHEN** `async for` is used over an ordered stream that reports itself as
  parallel
- **THEN** elements arrive in encounter order

#### Scenario: An already-extended stream refuses direct iteration

- **WHEN** `async for` is used over a `Stream` reference that has already been
  extended into a new instance
- **THEN** it raises `IllegalStateException`, as `iterator()` does on the same
  reference

### Requirement: Stream is a synchronous context manager

`Stream` SHALL implement `__enter__` and `__exit__`, so that
`with stream as s:` is supported directly, without wrapping the stream in
`contextlib.closing()`.

`__enter__` SHALL return the stream itself. `__exit__` SHALL call `close()` and
SHALL NOT suppress an exception propagating out of the `with` body.

This is parity rather than expansion: Java's `BaseStream` extends
`AutoCloseable` and its streams are usable in try-with-resources with no
wrapper, while the equivalent here has required one. Every rule of the
`stream-close-handling` capability applies unchanged, because `__exit__`
delegates to `close()` rather than restating what it does: every registered
handler runs, in registration order; a raising handler does not prevent later
handlers from running; and the first exception raised is the one propagated.

The protocol implemented SHALL be the synchronous one. Close handlers are
plain no-arg callables and `close()` does not await, so `with` is the protocol
that matches the contract as it stands; the asynchronous pair is deliberately
not part of this capability.

#### Scenario: A close handler runs on block exit

- **WHEN** a stream with a registered close handler is used as
  `with stream as s:` and the block completes normally
- **THEN** the handler has been invoked exactly once on exit

#### Scenario: __enter__ returns the stream itself

- **WHEN** `with stream as s:` is written
- **THEN** `s` **is** the stream that entered the block

#### Scenario: Handlers still run when the block raises

- **WHEN** the body of a `with` block over a stream with a registered close
  handler raises an exception
- **THEN** the handler has been invoked, and the exception propagates out of the
  `with` statement rather than being suppressed

#### Scenario: Every handler runs, in order

- **WHEN** a stream with handlers registered in the order `h1, h2` exits a
  `with` block
- **THEN** `h1` and `h2` have each been invoked once, in that order

#### Scenario: Entering is exempt from invalidation

- **WHEN** a `Stream` reference that has already been extended into a new
  instance is used as `with stream:`
- **THEN** it does not raise on account of invalidation, `on_close()` and
  `close()` being exempt from it

### Requirement: Stream has an informative repr

`Stream` SHALL implement `__repr__`, returning a string that identifies the
stream's concrete type and reports its queued chain of intermediate operations
and its execution mode.

The repr SHALL NOT pull any element from the source, SHALL NOT compose the
chain, and SHALL NOT raise on a stream in any state — including one that has
already been extended or terminally consumed — since a debugger or error
formatter may render it at any point.

#### Scenario: The repr names the type, the chain and the mode

- **WHEN** `repr()` is called on a parallel stream carrying a queued chain of
  intermediate operations
- **THEN** the returned string identifies the stream's concrete type, indicates
  the queued operations, and indicates that the stream is parallel

#### Scenario: The repr pulls nothing

- **WHEN** `repr()` is called on a stream whose pipeline carries an observable
  side effect
- **THEN** no element has been pulled and no side effect has been observed

#### Scenario: The repr of an extended stream does not raise

- **WHEN** `repr()` is called on a `Stream` reference that has already been
  extended into a new instance
- **THEN** it returns a string rather than raising

### Requirement: Truth testing a Stream raises

`Stream` SHALL implement `__bool__` to raise `TypeError`. `bool(stream)`,
`if stream:`, `not stream`, and any other implicit truth test SHALL raise
rather than return a value.

There is no correct synchronous answer available: whether a stream is empty can
only be determined by consuming it, and consumption is asynchronous. Without
this requirement Python's default applies and every `Stream` — including an
empty one — is truthy, which is a silently wrong answer to a question the caller
plainly meant to ask. A loud refusal is preferred to that, and this is the one
place the library deliberately refuses an operation Python permits on other
objects.

The raised message SHALL name the asynchronous alternatives, so a caller who
meant "is this stream empty" is directed to a terminal operation that can answer.

#### Scenario: bool() on a stream raises

- **WHEN** `bool(stream)` is called
- **THEN** it raises `TypeError`

#### Scenario: An implicit truth test raises

- **WHEN** a stream is used in a boolean context, such as `if stream:` or
  `not stream`
- **THEN** it raises `TypeError`

#### Scenario: An empty stream is not silently truthy

- **WHEN** a stream known to contain no elements is used in a boolean context
- **THEN** it raises `TypeError` rather than evaluating as true

#### Scenario: The message points at an asynchronous alternative

- **WHEN** the `TypeError` raised by a truth test is inspected
- **THEN** its message names an asynchronous way to ask the question the caller
  was attempting

### Requirement: The addition operator concatenates two streams

`Stream` SHALL implement `__add__`, so that `a + b` returns the same stream
`Stream.concat(a, b)` returns, for two `Stream` operands.

This is the one member of this capability with no counterpart in Java's API and
is a deliberate expansion rather than a parity fix. `Stream.concat()` remains the
contract: `__add__` SHALL delegate to it and SHALL add no behaviour of its own,
so the `stream-concat` capability governs the result entirely — its elements and
their order, its laziness, its close handlers, its execution mode, its ordering
characteristic, its concrete type, and its invalidation of both operands.

Adding a `Stream` to a non-`Stream` operand SHALL NOT be supported. `__add__`
SHALL return `NotImplemented` for such an operand so that Python raises its own
`TypeError`, rather than coercing the operand into a stream.

#### Scenario: Adding two streams concatenates them

- **WHEN** `a + b` is evaluated for two `Stream` instances and the result is
  consumed
- **THEN** it yields every element of `a`, in order, followed by every element of
  `b`, in order

#### Scenario: The operator result matches concat exactly

- **WHEN** `a + b` is evaluated
- **THEN** the resulting stream's execution mode, ordering characteristic,
  concrete type and close handlers are those the `stream-concat` capability
  requires of `Stream.concat(a, b)`

#### Scenario: The operator invalidates both operands

- **WHEN** `c = a + b` is evaluated and an operation is then attempted on `a`
- **THEN** it raises `IllegalStateException`

#### Scenario: Adding a non-stream raises

- **WHEN** a `Stream` is added to a list, a string, or any non-`Stream` object
- **THEN** a `TypeError` is raised, and the non-`Stream` operand is not coerced
  into a stream

### Requirement: The synchronous value protocols are refused, not implemented

`Stream` SHALL NOT implement `__len__`, `__iter__`, `__contains__`,
`__getitem__`, `__reversed__`, or `__eq__`. Each demands a value synchronously,
and every terminal operation on a `Stream` is a coroutine, so none can be
satisfied without either consuming the stream behind the caller's back or
returning a wrong answer.

`__getitem__` SHALL remain unimplemented for a second, independent reason:
Python synthesizes an iterator from `__getitem__` when `__iter__` is absent, so
defining it would make `for element in stream` appear to work while calling
`stream[0]`, `stream[1]`, and so on indefinitely. Slicing a stream is expressible
today with `skip()` and `limit()`, which is also what Java offers.

These exclusions SHALL be recorded rather than left implicit, so that a later
reader finds a decision. Where an excluded protocol has a wrong silent default,
that default is closed by an explicit requirement in this capability rather than
by adding the protocol — `__bool__` above being the case in point.

#### Scenario: Synchronous iteration is refused

- **WHEN** `for element in stream` or `list(stream)` is attempted
- **THEN** a `TypeError` is raised, and no element is pulled from the source

#### Scenario: Length is refused

- **WHEN** `len(stream)` is called
- **THEN** a `TypeError` is raised

#### Scenario: Membership testing is refused

- **WHEN** `element in stream` is evaluated
- **THEN** a `TypeError` is raised, and the stream is not consumed

#### Scenario: Subscripting is refused

- **WHEN** `stream[0]` or `stream[1:3]` is evaluated
- **THEN** a `TypeError` is raised

#### Scenario: Equality remains identity

- **WHEN** two distinct `Stream` instances built over equal sources are compared
  with `==`
- **THEN** the comparison is `False`, the default identity comparison applying,
  and neither stream is consumed
