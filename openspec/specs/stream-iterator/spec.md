## Purpose

Defines the contract for `Stream.iterator()`, an escape-hatch terminal-ish operation that composes a stream's currently-queued chain of intermediate operations into an executable `AsyncGenerator` and hands it to the caller without pulling any elements from it. Unlike other terminal operations, `iterator()` does not drive consumption itself — the caller does, via `async for`, direct `__anext__()` calls, or partial consumption — and, like other terminal operations, it composes non-destructively so the stream instance remains valid for further use afterward. Applies under `SEQUENTIAL` and `RACING` alike, with no mode-specific override; because it hands out raw elements, the order they arrive in is part of its contract, and an ordered `RACING` stream yields in encounter order.

## Requirements

### Requirement: iterator() exposes the composed pipeline without consuming it
`Stream.iterator()` SHALL compose the stream's currently-queued chain of intermediate operations and return the resulting `AsyncGenerator[T, None]` to the caller, without pulling any elements from it. The caller SHALL be responsible for driving iteration (e.g. via `async for`, direct `__anext__()` calls, or partial consumption).

#### Scenario: iterator() returns an async generator without consuming it
- **WHEN** `.iterator()` is called on a `Stream` with a queued chain of intermediate operations
- **THEN** the call returns an `AsyncGenerator` and no elements have yet been pulled from the underlying source

#### Scenario: Caller drives consumption via async for
- **WHEN** a caller iterates the object returned by `.iterator()` with `async for`
- **THEN** it yields the same elements, in the same order, that a terminal operation like `collect(to_list())` would have produced for an equivalent chain

#### Scenario: Caller can partially consume the iterator
- **WHEN** a caller pulls only some elements from the object returned by `.iterator()` (e.g. by calling `__anext__()` a few times) and then stops
- **THEN** no error occurs, and only the elements actually pulled are computed through the chain

### Requirement: iterator() works identically for sequential and parallel streams
`Stream.iterator()` SHALL work under either executor — sequential composition, linking the chain onto one sink via `_wrap_sink()`, or racing composition — without requiring any mode-specific override, relying on the executor's element-producing operation.

`iterator()` hands raw elements to the caller, so the order they arrive in is
definitionally observable. It SHALL therefore declare to the executor that it
observes encounter order: on an ordered racing stream the returned generator
SHALL yield in encounter order, matching what `collect(to_list())` on the same
stream produces. On a stream the caller has declared `unordered()`, it SHALL
yield in whatever order the race resolves elements, at the racing executor's
unmodified cost.

`collect(to_generator)`, which composes through the same element-producing
operation, SHALL follow the same rule.

#### Scenario: iterator() under RACING execution
- **WHEN** `.iterator()` is called on a stream using `RACING` execution with a
  queued chain of intermediate operations and no `unordered()`
- **THEN** the returned `AsyncGenerator`, when iterated, yields the elements the
  racing composition would produce, in encounter order

#### Scenario: iterator() under RACING execution on an unordered stream
- **WHEN** `.iterator()` is called on a stream using `RACING` execution with
  `.unordered()` queued
- **THEN** the returned `AsyncGenerator` yields those elements as racing branches
  resolve them, in no guaranteed order, following the racing executor's existing
  execution semantics

#### Scenario: to_generator matches iterator()
- **WHEN** `collect(to_generator)` is called on an ordered racing stream
- **THEN** the returned `AsyncGenerator` yields in encounter order, as
  `iterator()` on the same stream does

### Requirement: iterator() does not consume or mutate the chain
Calling `Stream.iterator()` SHALL follow the same non-destructive composition contract as other terminal operations: it SHALL NOT mutate or drain `self._chain`, so the stream instance remains valid for a subsequent call to `iterator()` or another terminal operation.

#### Scenario: A second terminal operation after iterator()
- **WHEN** `.iterator()` is called on a `Stream` and the returned generator is fully consumed, and then a different terminal operation (e.g. `collect(to_list())`) is called on the same `Stream` instance
- **THEN** the second call composes against the same chain of intermediate operations as the first, rather than against an empty chain
