## MODIFIED Requirements

### Requirement: iterator() works identically for sequential and parallel streams
`BaseStream.iterator()` SHALL work on both `Stream` (sequential composition, linking the chain onto one sink via `_wrap_sink()`) and `ParallelStream` (parallel composition via `_parallel()`) without requiring a subclass-specific override, relying on each subclass's existing `_compose()` implementation.

#### Scenario: iterator() on a ParallelStream
- **WHEN** `.iterator()` is called on a `ParallelStream` with a queued chain of intermediate operations
- **THEN** the returned `AsyncGenerator`, when iterated, yields the elements the parallel composition would produce (racing branches, unordered), following `ParallelStream`'s existing execution semantics
