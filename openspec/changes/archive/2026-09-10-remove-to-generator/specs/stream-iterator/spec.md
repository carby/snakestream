## REMOVED Requirements

### Requirement: iterator() works identically for sequential and parallel streams

**Reason**: Replaced by the requirement below, renamed to carry the uniqueness
clause that removing `collect(to_generator)` establishes. Its "to_generator
matches iterator()" scenario existed only to pin a second spelling to the
first, and there is no second spelling left to pin.

**Migration**: None for a caller of `iterator()` — every guarantee it made is
restated verbatim below. A caller of `collect(to_generator)` migrates to
`iterator()`, which is what that call already did internally.

## ADDED Requirements

### Requirement: iterator() works identically for sequential and parallel streams, and is the only route to the composed generator
`Stream.iterator()` SHALL work under either executor — sequential composition, linking the chain onto one sink via `_wrap_sink()`, or fork-join composition — without requiring any mode-specific override, relying on the executor's element-producing operation.

`iterator()` hands raw elements to the caller, so the order they arrive in is
definitionally observable. It SHALL therefore declare to the executor that it
observes encounter order: on an ordered parallel stream the returned generator
SHALL yield in encounter order, matching what `collect(to_list())` on the same
stream produces. On a stream the caller has declared `unordered()`, it SHALL
yield in whatever order the batches resolve elements, at the fork-join
executor's unmodified cost.

`iterator()` SHALL be the only operation on `Stream` that returns the composed
`AsyncGenerator` to the caller. No collector SHALL offer a second route to it,
so the rule above has exactly one subject and cannot be stated twice and drift.

#### Scenario: iterator() under RACING execution
- **WHEN** `.iterator()` is called on a stream using `RACING` execution with a
  queued chain of intermediate operations and no `unordered()`
- **THEN** the returned `AsyncGenerator`, when iterated, yields the elements the
  fork-join composition would produce, in encounter order

#### Scenario: iterator() under RACING execution on an unordered stream
- **WHEN** `.iterator()` is called on a stream using `RACING` execution with
  `.unordered()` queued
- **THEN** the returned `AsyncGenerator` yields those elements as batches
  resolve them, in no guaranteed order, following the fork-join executor's
  existing execution semantics

#### Scenario: There is no second route to the composed generator
- **WHEN** a caller wants the composed `AsyncGenerator` for a stream
- **THEN** `iterator()` returns it, iterating the stream directly yields from it, and no argument to `collect()` produces one
