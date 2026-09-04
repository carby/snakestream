## MODIFIED Requirements

### Requirement: Stream is asynchronously iterable

`Stream` SHALL implement `__aiter__`, so that `async for element in stream` is
supported directly and is equivalent to `async for element in stream.iterator()`.

`__aiter__` SHALL delegate to `iterator()` rather than reimplement it, and SHALL
therefore inherit that capability's contract in full: composition of the queued
chain without pulling any element, the caller driving iteration, the
non-destructive composition that leaves the stream instance usable afterwards,
and the declaration that the order elements arrive in is observable — so an
ordered stream under the fork-join executor yields in encounter order through
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
