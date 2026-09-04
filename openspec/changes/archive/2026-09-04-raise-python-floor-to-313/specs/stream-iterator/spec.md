## MODIFIED Requirements

### Requirement: iterator() exposes the composed pipeline without consuming it
`Stream.iterator()` SHALL compose the stream's currently-queued chain of intermediate operations and return the resulting `AsyncGenerator[T]` to the caller, without pulling any elements from it. The caller SHALL be responsible for driving iteration (e.g. via `async for`, direct `__anext__()` calls, or partial consumption).

The written form `AsyncGenerator[T]` denotes the same type the spec previously wrote as `AsyncGenerator[T, None]`: PEP 696 gives the send parameter a default of `None`, so the shorter spelling is the same contract, not a relaxed one. The generator SHALL still be one nothing is sent into.

#### Scenario: iterator() returns an async generator without consuming it
- **WHEN** `.iterator()` is called on a `Stream` with a queued chain of intermediate operations
- **THEN** the call returns an `AsyncGenerator` and no elements have yet been pulled from the underlying source

#### Scenario: Caller drives consumption via async for
- **WHEN** a caller iterates the object returned by `.iterator()` with `async for`
- **THEN** it yields the same elements, in the same order, that a terminal operation like `collect(to_list())` would have produced for an equivalent chain

#### Scenario: Caller can partially consume the iterator
- **WHEN** a caller pulls only some elements from the object returned by `.iterator()` (e.g. by calling `__anext__()` a few times) and then stops
- **THEN** no error occurs, and only the elements actually pulled are computed through the chain
