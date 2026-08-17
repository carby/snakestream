## ADDED Requirements

### Requirement: for_each_ordered() invokes the consumer in encounter order
`Stream.for_each_ordered(consumer)` SHALL invoke `consumer` once per element of the composed stream, in the stream's encounter order, and SHALL NOT return a value (matching `for_each()`'s `None` return).

#### Scenario: Sequential Stream preserves source order
- **WHEN** `Stream.of([1, 2, 3, 4]).for_each_ordered(consumer)` is called
- **THEN** `consumer` is invoked with `1`, then `2`, then `3`, then `4`, in that order

#### Scenario: Both sync and async consumers are supported
- **WHEN** `for_each_ordered()` is called with a synchronous consumer, and separately with an `async def` consumer
- **THEN** both invocations complete successfully, each consumer call awaited if it returns an awaitable, matching `for_each()`'s existing sync/async dispatch convention

### Requirement: for_each_ordered() preserves encounter order on ParallelStream
`Stream.for_each_ordered(consumer)`, when called on a `ParallelStream` instance, SHALL invoke `consumer` in the stream's encounter order, even though `ParallelStream._compose()`'s racing-branch execution model does not itself preserve order and `for_each()` on the same instance makes no such guarantee.

#### Scenario: ParallelStream yields ordered results via for_each_ordered
- **WHEN** a `ParallelStream` built from an ordered source (e.g. `Stream.of([1, 2, 3, 4]).parallel()`) has `.for_each_ordered(consumer)` called on it
- **THEN** `consumer` is invoked with `1`, then `2`, then `3`, then `4`, in that order — the same order `for_each_ordered()` would produce on the equivalent sequential `Stream`

#### Scenario: for_each_ordered does not alter for_each's behavior
- **WHEN** `for_each()` is called on a `ParallelStream` (unrelated to any `for_each_ordered()` call)
- **THEN** `for_each()`'s existing unordered-completion behavior is unchanged
