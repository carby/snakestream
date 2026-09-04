## MODIFIED Requirements

### Requirement: iterator() works identically for sequential and parallel streams
`Stream.iterator()` SHALL work under either executor — sequential composition, linking the chain onto one sink via `_wrap_sink()`, or fork-join composition — without requiring any mode-specific override, relying on the executor's element-producing operation.

`iterator()` hands raw elements to the caller, so the order they arrive in is
definitionally observable. It SHALL therefore declare to the executor that it
observes encounter order: on an ordered parallel stream the returned generator
SHALL yield in encounter order, matching what `collect(to_list())` on the same
stream produces. On a stream the caller has declared `unordered()`, it SHALL
yield in whatever order the batches resolve elements, at the fork-join
executor's unmodified cost.

`collect(to_generator)`, which composes through the same element-producing
operation, SHALL follow the same rule.

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

#### Scenario: to_generator matches iterator()
- **WHEN** `collect(to_generator)` is called on an ordered racing stream
- **THEN** the returned `AsyncGenerator` yields in encounter order, as
  `iterator()` on the same stream does
