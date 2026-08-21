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
