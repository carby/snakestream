## ADDED Requirements

### Requirement: Building a composed pipeline does not recurse per chained operation

`BaseStream._compose()` (and the `_sequential()` helper it uses for sequential composition) SHALL build the executable pipeline without recursing once per queued intermediate-operation closure. Building (as opposed to consuming) a chain of intermediate operations SHALL NOT fail with `RecursionError` regardless of how many operations are queued, up to ordinary Python list-size limits.

Note: this requirement covers only the build-time traversal in `_sequential()`/`_compose()`. It does not cover recursion that may still occur while *consuming* the composed pipeline, since each individual intermediate operation's own implementation (e.g. `async for i in iterable: yield ...` in `stream.py`) independently delegates to its upstream operation at consumption time — that is a separate concern, not addressed by this requirement.

#### Scenario: A long chain of intermediate operations builds successfully

- **WHEN** `BaseStream._sequential()` is called with a long list of queued closures (deep enough that the previous per-op-recursion implementation would approach Python's default recursion limit)
- **THEN** building the composed pipeline completes without raising `RecursionError`
