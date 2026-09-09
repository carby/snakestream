## MODIFIED Requirements

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

Delegation SHALL be total: because `__exit__` calls `close()` and restates
nothing, a stream carrying a handler that `close()` refuses is refused under
`with` on exactly the same terms, at block exit. `with` SHALL NOT be given a
capability `close()` lacks, and the asynchronous pair SHALL NOT be reachable
through it.

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

#### Scenario: An async handler is refused at block exit

- **WHEN** a stream carrying a handler `close()` refuses is used as
  `with stream as s:` and the block completes normally
- **THEN** the same failure `close()` raises propagates out of the `with`
  statement, rather than the handler being skipped or the block succeeding

## ADDED Requirements

### Requirement: Stream is an asynchronous context manager

`Stream` SHALL implement `__aenter__` and `__aexit__`, so that
`async with stream as s:` is supported directly, without wrapping the stream in
`contextlib.aclosing()`.

`__aenter__` SHALL return the stream itself, matching `__enter__`. `__aexit__`
SHALL await `aclose()` and SHALL NOT suppress an exception propagating out of
the `async with` body.

Every rule of the `stream-close-handling` capability applies unchanged, because
`__aexit__` delegates to `aclose()` rather than restating what it does: every
registered handler runs, one at a time, in registration order; an awaitable
result is awaited; a failing handler does not prevent later handlers from
running; and the first failure in encounter order is the one propagated, with
the later ones attached to it as notes.

Both protocols SHALL be implemented, and the synchronous one SHALL NOT be
removed or narrowed. They are not alternatives to choose between: `with`
remains correct — and remains what the documented subclassed-resource examples
use — for a stream whose handlers are all synchronous, and is the only protocol
available to a synchronous caller. `async with` is what a stream carrying an
awaitable handler requires.

Supporting the asynchronous protocol on the same terms as the synchronous one
also makes `contextlib.aclosing(stream)` work by construction, mirroring
`contextlib.closing(stream)`. That mirror is a consequence of implementing
`aclose()`, not a separate promise.

#### Scenario: An async close handler runs on block exit

- **WHEN** a stream with a registered `async def` close handler is used as
  `async with stream as s:` and the block completes normally
- **THEN** the handler has run to completion on exit, with no un-awaited
  coroutine left behind

#### Scenario: __aenter__ returns the stream itself

- **WHEN** `async with stream as s:` is written
- **THEN** `s` **is** the stream that entered the block

#### Scenario: Handlers still run when the block raises

- **WHEN** the body of an `async with` block over a stream with a registered
  close handler raises an exception
- **THEN** the handler has been invoked, and the exception propagates out of the
  `async with` statement rather than being suppressed

#### Scenario: Sync handlers work under the async protocol

- **WHEN** a stream whose registered handlers are all plain sync callables is
  used as `async with stream as s:`
- **THEN** every handler has been invoked exactly once, in registration order,
  and nothing is refused

#### Scenario: Every handler runs, in order, and the first failure propagates

- **WHEN** an `async with` block exits over a stream with three failing
  handlers registered in order, mixing sync and async
- **THEN** all three have run, the first failure propagates out of the
  statement, and it carries a note per later failure

#### Scenario: Entering is exempt from invalidation

- **WHEN** a `Stream` reference that has already been extended into a new
  instance is used as `async with stream:`
- **THEN** it does not raise on account of invalidation, `on_close()`,
  `close()` and `aclose()` being exempt from it

#### Scenario: The stream is usable inside the block

- **WHEN** a stream is entered with `async with stream as s:` and consumed
  inside the block
- **THEN** entering has neither consumed nor advanced it, and the consumption
  inside the block behaves as it would outside one
