## Purpose

Defines the contract for `Stream.for_each_ordered(consumer)`, an ordered variant of `for_each()` that invokes the consumer in the stream's encounter order, even under `RACING` execution whose racing-branch execution model does not otherwise preserve order. Mirrors Java's `Stream.forEachOrdered()`, including the javadoc's "if the stream has a defined encounter order" caveat: a pipeline whose queued operations have cleared the ordering characteristic (see `stream-ordering`) has none, so there the guarantee is released and the call runs under the stream's own executor rather than forfeiting concurrency — the same split Java's `ForEachOps` makes between `ForEachOrderedTask` and `ForEachTask`.

## Requirements

### Requirement: for_each_ordered() invokes the consumer in encounter order
`Stream.for_each_ordered(consumer)` SHALL invoke `consumer` once per element of the composed stream, in the stream's encounter order, and SHALL NOT return a value (matching `for_each()`'s `None` return).

#### Scenario: Sequential Stream preserves source order
- **WHEN** `Stream.of([1, 2, 3, 4]).for_each_ordered(consumer)` is called
- **THEN** `consumer` is invoked with `1`, then `2`, then `3`, then `4`, in that order

#### Scenario: Both sync and async consumers are supported
- **WHEN** `for_each_ordered()` is called with a synchronous consumer, and separately with an `async def` consumer
- **THEN** both invocations complete successfully, each consumer call awaited if it returns an awaitable, matching `for_each()`'s existing sync/async dispatch convention

### Requirement: for_each_ordered() preserves encounter order under RACING execution
`Stream.for_each_ordered(consumer)`, when called on an **ordered** stream whose
executor is `RACING` (i.e. `.parallel()` was the last mode switch before this
call), SHALL invoke `consumer` in the stream's encounter order, even though
`RACING`'s branch-racing execution does not itself preserve order and
`for_each()` on the same stream makes no such guarantee. A stream is ordered
for this purpose unless the pipeline's queued operations have cleared the
ordering characteristic; see the `stream-ordering` capability.

#### Scenario: A RACING stream yields ordered results via for_each_ordered
- **WHEN** a stream built from an ordered source and switched to `RACING`
  execution (e.g. `Stream.of([1, 2, 3, 4]).parallel()`) has
  `.for_each_ordered(consumer)` called on it
- **THEN** `consumer` is invoked with `1`, then `2`, then `3`, then `4`, in that
  order — the same order `for_each_ordered()` would produce on the equivalent
  `SEQUENTIAL` stream

#### Scenario: for_each_ordered does not alter for_each's behavior
- **WHEN** `for_each()` is called on a stream using `RACING` execution
  (unrelated to any `for_each_ordered()` call)
- **THEN** `for_each()`'s existing unordered-completion behavior is unchanged

### Requirement: for_each_ordered() is released from the encounter-order guarantee on an unordered pipeline
`Stream.for_each_ordered(consumer)` SHALL, when the pipeline's ordering
characteristic is unordered, invoke `consumer` under the stream's own executor
rather than forcing sequential execution — making it equivalent to `for_each()`
for such a pipeline, and forfeiting no concurrency the caller has asked for.

This is the behaviour Java's own `forEachOrdered()` has: it selects an ordered
traversal only when the upstream pipeline is known to be ordered, and falls
back to the unordered traversal otherwise. It is also the meaning of the
javadoc's "in the encounter order of the stream if the stream has a defined
encounter order" caveat — a stream on which `unordered()` has been declared is
exactly a stream with no defined encounter order.

`consumer` SHALL still be invoked exactly once per element, and SHALL still be
awaited if it returns an awaitable, in both the ordered and unordered cases.

#### Scenario: An unordered parallel pipeline is not forced sequential
- **WHEN** `.unordered()` is queued on a parallel stream carrying a chain whose
  steps complete out of encounter order (e.g. a `.map()` with per-element
  variable delay), and `.for_each_ordered(consumer)` is awaited
- **THEN** the consumer is invoked once per element, and the call is permitted
  to run its branches concurrently rather than pulling strictly in encounter
  order

#### Scenario: Every element is still delivered exactly once when unordered
- **WHEN** `.for_each_ordered(consumer)` is awaited on an unordered pipeline
- **THEN** the consumer receives every element of the pipeline exactly once,
  and the awaited call returns `None`

#### Scenario: sorted() after unordered() restores the ordered guarantee
- **WHEN** `.unordered()` is queued on a parallel stream, followed by
  `.sorted(c)`, and `.for_each_ordered(consumer)` is awaited
- **THEN** the consumer is invoked in the sorted encounter order, because
  `sorted()` restores the ordering characteristic downstream
