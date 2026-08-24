## MODIFIED Requirements

### Requirement: Building a composed pipeline does not recurse per chained operation

`Stream._compose()` (and the `_wrap_sink()` helper it uses to link the sink chain) SHALL build the executable pipeline without recursing once per queued intermediate operation. Building (as opposed to consuming) a chain of intermediate operations SHALL NOT fail with `RecursionError` regardless of how many operations are queued, up to ordinary Python list-size limits.

Note: this requirement covers only the build-time traversal that links the sink chain. It does not cover recursion that occurs while *consuming* the composed pipeline: each intermediate sink's `accept()` calls `downstream.accept()`, so pushing one element through a chain of *k* operations is O(k) stack-deep. That is a separate concern, not addressed by this requirement, and is unchanged by the push-based redesign — the same O(k) per-element depth existed under the previous `async for`/`__anext__()` delegation model, and Java's own `Sink.ChainedReference` has it too.

#### Scenario: A long chain of intermediate operations builds successfully

- **WHEN** the sink-chain linking helper is called with a long list of queued operations (deep enough that a per-op-recursive implementation would approach Python's default recursion limit)
- **THEN** linking the sink chain completes without raising `RecursionError`
