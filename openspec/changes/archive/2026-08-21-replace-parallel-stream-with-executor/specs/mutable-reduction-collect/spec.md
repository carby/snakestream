## MODIFIED Requirements

### Requirement: `combiner` is accepted but not invoked
The third argument, `combiner`, SHALL be accepted for signature parity with Java's `Stream.collect(Supplier, BiConsumer, BiConsumer)` but SHALL NOT be called by this implementation, under either executor. Both fold over a single composed `AsyncGenerator` with no independently-accumulated partitions to merge, matching the existing `reduce(identity, accumulator)` behavior under `.parallel()`.

#### Scenario: `combiner` is never called, sequential
- **WHEN** `Stream.of([1, 2, 3]).collect(list, list.append, combiner)` is called with a `combiner` that records its own invocations
- **THEN** the result is `[1, 2, 3]` and `combiner` was never called

#### Scenario: `combiner` is never called, parallel
- **WHEN** the same 3-arg `collect()` call is made on a parallel stream
- **THEN** the returned container holds all source elements (order not guaranteed) and `combiner` was never called
