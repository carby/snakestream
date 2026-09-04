## MODIFIED Requirements

### Requirement: A parallel stream's terminal accumulates across all branches

When a terminal sink is driven under the fork-join executor, it SHALL receive
every element that the batches produce, exactly once each, and SHALL produce
the same result the same terminal produces under the sequential executor for
any order-independent operation.

A short-circuiting terminal under the fork-join executor SHALL stop consuming
once its result is fixed, and SHALL leave no in-flight batch uncancelled or its
exception unretrieved.

Cancellation under the fork-join executor SHALL reach the loop dispatching
batches, but NOT the sinks inside an in-flight batch: each batch holds its own
sink chain and the terminal is not a member of it. A batch's own `limit()` or
`flat_map()` therefore SHALL NOT be expected to stop on a terminal's behalf.

#### Scenario: A parallel terminal sees every element once
- **WHEN** `count()` or `reduce()` is called on a parallel stream over a source with many elements
- **THEN** the result reflects every source element exactly once, matching the sequential result

#### Scenario: A parallel short-circuiting terminal tears down cleanly
- **WHEN** `any_match(predicate)` is called on a parallel stream and an early element satisfies `predicate`
- **THEN** it returns `True` and no unhandled exception or warning escapes from the abandoned batches
