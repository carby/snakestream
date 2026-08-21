## MODIFIED Requirements

### Requirement: iterator() works identically for sequential and parallel streams
`BaseStream.iterator()` SHALL work under either executor — sequential composition, linking the chain onto one sink via `_wrap_sink()`, or racing composition — without requiring any mode-specific override, relying on the executor's element-producing operation.

#### Scenario: iterator() on a ParallelStream
- **WHEN** `.iterator()` is called on a parallel stream with a queued chain of intermediate operations
- **THEN** the returned `AsyncGenerator`, when iterated, yields the elements the racing composition would produce (racing branches, unordered), following the racing executor's existing execution semantics
