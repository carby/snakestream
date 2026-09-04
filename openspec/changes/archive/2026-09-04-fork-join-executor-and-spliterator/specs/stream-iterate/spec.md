## MODIFIED Requirements

### Requirement: iterate() composes like any other stream

The stream returned by `Stream.iterate()` SHALL support the full intermediate
and terminal operation surface, including with an async `nxt`, and SHALL be
usable under the fork-join executor via `.parallel()`. Because the sequence is
infinite, a terminal operation SHALL only be reached through a
short-circuiting operation such as `limit()` or a short-circuiting terminal.

#### Scenario: Intermediate operations over an async-nxt iterate

- **WHEN** `Stream.iterate(0, nxt).map(m).filter(p).limit(3)` is collected,
  where `nxt` is an `async def`
- **THEN** the result is the same as for the equivalent sync `nxt`

#### Scenario: Racing executor over an async-nxt iterate

- **WHEN** `Stream.iterate(0, nxt).parallel().limit(10)` is collected, where
  `nxt` is an `async def`
- **THEN** ten elements are produced and none of them is a coroutine object
