## Purpose

Defines `Stream.iterate(seed, nxt)` — the static factory producing the infinite
ordered sequence `seed, nxt(seed), nxt(nxt(seed)), ...` — covering what it
yields, how lazily it calls `nxt`, and the fact that `nxt` may be supplied in
any of the sync/async function or callable-object forms the library accepts
everywhere else.

## Requirements

### Requirement: iterate() produces the iterative sequence, lazily

`Stream.iterate(seed, nxt)` SHALL be an ordinary (non-`async`) static method
returning a `Stream` whose elements are `seed`, then the result of applying
`nxt` to `seed`, then the result of applying `nxt` to that, and so on without
bound. The resulting stream SHALL be ordered and sequential.

`nxt` SHALL NOT be called at construction time, and SHALL be called exactly
once per element produced beyond the seed. A pipeline that consumes only the
first `n` elements SHALL call `nxt` exactly `n - 1` times.

#### Scenario: The seed is the first element

- **WHEN** `Stream.iterate(0, lambda n: n + 1)` is consumed for three elements
- **THEN** the elements produced are exactly `0, 1, 2`, in that order

#### Scenario: No work at construction time

- **WHEN** `Stream.iterate(seed, nxt)` is called but the result is never
  consumed
- **THEN** `nxt` is not called

#### Scenario: nxt is called once per element beyond the seed

- **WHEN** a stream from `Stream.iterate(0, nxt)` is limited to five elements
  and fully consumed
- **THEN** `nxt` has been called exactly four times

#### Scenario: A non-scalar seed is a single element

- **WHEN** `Stream.iterate((0, 1), lambda n: (n[1], n[0] + n[1]))` is consumed
  for five elements
- **THEN** the elements produced are exactly the tuples `(0, 1)`, `(1, 1)`,
  `(1, 2)`, `(2, 3)`, `(3, 5)`, each one element of the stream

### Requirement: iterate() accepts sync and async nxt alike

`nxt` SHALL be dispatched through the same mechanism as every other
user-supplied callable in the library, per the `callable-dispatch` capability:
a plain sync function, an `async def` function, a callable object with a sync
`__call__`, and a callable object with an async `__call__` SHALL all produce
the same elements. Where `nxt`'s result is awaitable it SHALL be awaited before
being yielded and before being passed back into `nxt` for the next element.
`iterate()` SHALL NOT yield an un-awaited awaitable as a stream element.

Awaitability SHALL be classified once per stream rather than once per element,
consistent with "Awaitability is classified once per composition" in the
`callable-dispatch` capability.

#### Scenario: Async function nxt

- **WHEN** `Stream.iterate(0, nxt)` is consumed for three elements, where `nxt`
  is `async def nxt(x): return x + 1`
- **THEN** the elements produced are exactly `0, 1, 2`, and no element is a
  coroutine object

#### Scenario: Sync function nxt is unaffected

- **WHEN** `Stream.iterate(0, nxt)` is consumed, where `nxt` is a plain sync
  function
- **THEN** the elements produced are the same as they were before async `nxt`
  was supported

#### Scenario: Callable object nxt, sync and async

- **WHEN** `Stream.iterate(0, nxt)` is consumed for three elements, where `nxt`
  is a class instance implementing `__call__` — once with a sync `__call__`,
  once with an async `__call__`
- **THEN** both produce exactly `0, 1, 2`

#### Scenario: Sync-signatured nxt returning a coroutine

- **WHEN** `Stream.iterate(0, nxt)` is consumed, where `nxt` is declared with a
  plain `def` but returns a coroutine
- **THEN** the coroutine is awaited and the awaited values are the stream's
  elements

### Requirement: iterate() composes like any other stream

The stream returned by `Stream.iterate()` SHALL support the full intermediate
and terminal operation surface, including with an async `nxt`, and SHALL be
usable under a racing executor via `.parallel()`. Because the sequence is
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
