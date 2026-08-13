## Purpose

Defines the contract for `Stream.reduce(accumulator)`, the 1-arg overload of `reduce` that folds a stream using its own first pulled element as the seed instead of requiring an externally supplied identity value, mirroring Java's `Optional<T> reduce(BinaryOperator<T>)`. Covers accumulator dispatch (sync and async), the `None`-on-empty and short-circuit-on-single-element edge cases, and the guarantee that the existing 2-arg `reduce(identity, accumulator)` overload is unaffected.

## Requirements

### Requirement: reduce() accepts an accumulator with no identity
`Stream.reduce(accumulator)` SHALL fold the composed stream using its own first pulled element as the seed, requiring no externally supplied identity value. `accumulator` SHALL accept two values of the stream's element type and return a value of that same type, matching Java's `BinaryOperator<T>`. Both sync and async accumulators SHALL be accepted, dispatched the same way the existing 2-arg `reduce(identity, accumulator)` dispatches its accumulator.

#### Scenario: Multi-element stream folds left starting from the first element
- **WHEN** `Stream.reduce(accumulator)` is called on a stream yielding elements `e1, e2, ..., en` in order
- **THEN** the result equals `accumulator(...accumulator(accumulator(e1, e2), e3)..., en)`, the same left-fold order as the 2-arg form with `e1` as identity

#### Scenario: Async accumulator is awaited
- **WHEN** `Stream.reduce(accumulator)` is called with an `async def` accumulator on a multi-element stream
- **THEN** each accumulator call is awaited before its result is used as the next fold input, and the final result is the awaited value, not a coroutine

### Requirement: Empty stream returns None without calling the accumulator
When the composed stream yields no elements, `Stream.reduce(accumulator)` SHALL return `None` without ever calling `accumulator`, following the same `T | None` convention already used by `find_any()`, `max()`, and `min()` rather than a wrapped `Optional[T]` type.

#### Scenario: Empty stream returns None
- **WHEN** `Stream.reduce(accumulator)` is called on a stream that yields no elements
- **THEN** the result is `None` and `accumulator` is never called

### Requirement: Single-element stream returns that element unchanged
When the composed stream yields exactly one element, `Stream.reduce(accumulator)` SHALL return that element without calling `accumulator`, matching Java's `Optional<T>`-of-the-sole-element behavior.

#### Scenario: Single-element stream short-circuits the accumulator
- **WHEN** `Stream.reduce(accumulator)` is called on a stream that yields exactly one element `e1`
- **THEN** the result is `e1` and `accumulator` is never called

### Requirement: Existing 2-arg reduce(identity, accumulator) is unchanged
Adding the 1-arg overload SHALL NOT change the behavior, signature, or return type of the existing `Stream.reduce(identity, accumulator)` overload.

#### Scenario: 2-arg reduce behavior is unaffected
- **WHEN** `Stream.reduce(identity, accumulator)` is called with an explicit identity, as before this change
- **THEN** the result is identical to the pre-change behavior: the accumulator is called once per element, starting from `identity`
