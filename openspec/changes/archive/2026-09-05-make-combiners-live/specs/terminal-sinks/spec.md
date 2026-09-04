## MODIFIED Requirements

### Requirement: A parallel stream's terminal accumulates across all branches

When a terminal sink is driven under the fork-join executor, it SHALL
account for every element that the batches produce, exactly once each, and
SHALL produce the same result the same terminal produces under the
sequential executor for any order-independent operation.

Where the terminal declares `can_partition()` True (`sink-protocol`'s
partition protocol) and nothing in the chain needs a global view
(`parallel-reduction`), it SHALL NOT itself receive `accept()` for any
source element: each batch pushes into its own peer sink instead, and the
peer's accumulated container is folded into the terminal via `merge_from()`.
"Receives every element exactly once" therefore holds for the terminal's
*accumulation* — the value built by its container across every peer merge —
not for direct calls to the terminal's own `accept()`. Every other terminal
(`can_partition()` False, the ordinary case) is unaffected: it still
receives every element via `accept()` exactly as before.

A short-circuiting terminal under the fork-join executor SHALL stop
consuming once its result is fixed, and SHALL leave no in-flight batch
uncancelled or its exception unretrieved. This applies to a partitioning
terminal too: the partitioned driving loop checks
`cancellation_requested()` before pulling a further round and after each
peer merge, stopping in both places once the terminal's result is fixed -
though no terminal shipped today both partitions and short-circuits, so this
is a protocol guarantee rather than an exercised path.

Cancellation under the fork-join executor SHALL reach the loop dispatching
batches, but NOT the sinks inside an in-flight batch: each batch holds its
own sink chain (or, for a partitioning terminal, its own peer) and the
terminal is not a member of it. A batch's own `limit()` or `flat_map()`
therefore SHALL NOT be expected to stop on a terminal's behalf.

#### Scenario: A parallel terminal sees every element once
- **WHEN** `count()` or `reduce()` is called on a parallel stream over a source with many elements
- **THEN** the result reflects every source element exactly once, matching the sequential result

#### Scenario: A parallel short-circuiting terminal tears down cleanly
- **WHEN** `any_match(predicate)` is called on a parallel stream and an early element satisfies `predicate`
- **THEN** it returns `True` and no unhandled exception or warning escapes from the abandoned batches

#### Scenario: A partitioning terminal accounts for every element through its peers
- **WHEN** a `Collector` supplying a `combiner` collects a `.parallel()` stream spanning more than one batch
- **THEN** the terminal's own `accept()` is never called, every element reaches a peer's `accept()` exactly once, and the merged result equals the sequential result
