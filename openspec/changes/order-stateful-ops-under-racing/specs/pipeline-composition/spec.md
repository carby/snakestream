## MODIFIED Requirements

### Requirement: Parallel distinct() and limit() remain globally correct across branches
Under the racing executor, the `distinct()` and `limit()` steps SHALL produce results that are globally correct across all racing branches within a single composition: `distinct()` SHALL NOT yield the same element from two different branches, and `limit(n)` SHALL NOT yield more than `n` elements in total across all branches combined. This holds even though state is freshly initialized per composition (per the sequential requirement above applied at the composition level), by sharing one state instance across all branches of a given composition.

The racing executor SHALL build one state map per composition and pass that same map into every branch's `begin()`, so each branch's sinks for a given operation share one state instance.

These guarantees SHALL hold for every operation in the chain a terminal executes under the racing executor, including operations declared before the `.parallel()` call that selected it. Because the executor governs the whole pipeline rather than only the portion declared after the switch, strictly more chains reach this requirement than before; the mechanism is unchanged.

**Which** elements survive is a separate question from **how many**, and is settled by whether the pipeline carries an encounter-order requirement at that operation's position (see the `racing-encounter-order` capability). Where it does, `limit(n)` yields the first `n` in encounter order and `distinct()` keeps the earliest-encountered member of each equal group. Where it does not — the pipeline was declared `unordered()` — `limit(n)` yields the first `n` to arrive across all branches in whatever order the race resolves them, and `distinct()` keeps an arbitrary representative. The cardinality guarantees in this requirement hold identically in both cases; only the selection differs.

`limit(n)`'s check-and-reserve against the shared count SHALL be atomic with respect to racing branches: no suspension point SHALL occur between observing the count and reserving a slot. This applies wherever a count is shared across branches; where the pipeline is ordered and the operation is therefore not racing branch-against-branch, the requirement is satisfied trivially.

When the driving loop stops pulling because cancellation was requested and closes the shared upstream source, that closure SHALL be safe with respect to any other branch subsequently pulling from or closing the same shared source: no unhandled exception SHALL escape the racing executor's task loop as a result. This SHALL hold whether the cancelling operation sits inside a racing branch or downstream of an ordering barrier: cancellation raised downstream SHALL still reach and stop the upstream pull.

#### Scenario: Parallel distinct() does not yield cross-branch duplicates
- **WHEN** a chain containing `.distinct()` is composed under the racing executor against a source containing a repeated element, and multiple racing branches may each encounter that element
- **THEN** the composed output contains that element exactly once in total across all branches

#### Scenario: Parallel limit() does not exceed n in total
- **WHEN** a chain containing `.limit(n)` is composed under the racing executor against a source with more than `n` elements, racing across multiple branches
- **THEN** the composed output contains at most `n` elements in total across all branches

#### Scenario: Parallel state resets per composition
- **WHEN** a chain containing `.distinct()` or `.limit(n)` is composed under the racing executor and consumed once, and then the same chain is composed again against a new source
- **THEN** the second composition's shared state starts fresh, independent of what any branch observed during the first composition

#### Scenario: A second branch pulling from a closed shared source terminates cleanly
- **WHEN** a chain containing `.limit(n)` is composed under the racing executor and racing branch A closes the shared upstream source after the shared count reaches `n`, and racing branch B subsequently calls `__anext__()` on that same shared source
- **THEN** branch B's pull ends its local iteration (as a normal end-of-stream, not an unhandled exception) rather than propagating an error out of the racing executor

#### Scenario: A stateful op declared before .parallel() is still globally correct
- **WHEN** `.distinct()` is declared before `.parallel()` in a chain, so that it now runs under the racing executor
- **THEN** it yields each distinct element exactly once in total across all branches, exactly as it does when declared after the switch

#### Scenario: The cardinality guarantee holds on an ordered pipeline too
- **WHEN** a chain containing `.limit(n)` or `.distinct()` is composed under the racing executor on a pipeline that carries an encounter-order requirement at that operation's position
- **THEN** `limit(n)` still yields at most `n` elements in total and `distinct()` still yields each distinct element exactly once, with the selection determined by encounter order

### Requirement: Parallel skip() remains globally correct across branches
Under `RACING` execution, the `skip()` step SHALL drop exactly `n` elements
across all racing branches combined, not up to `n` elements per branch.

**Which** `n` are dropped depends on whether the pipeline carries an
encounter-order requirement at that operation's position (see the
`racing-encounter-order` capability). Where it does, `skip(n)` SHALL drop the
first `n` elements in encounter order, matching the sequential result. Where it
does not — the pipeline was declared `unordered()` — "first `n`" means the first
`n` elements pulled across all branches in whatever order the race resolves
them, which need not be the first `n` in source order.

The total-count guarantee is the same in both cases: exactly `n` elements are
dropped when the source has at least `n`, and the whole source is dropped when
it has fewer.

#### Scenario: Parallel skip() does not exceed n dropped in total
- **WHEN** a stream chain containing `.skip(n)` is run under `RACING`
  execution against a source with more than `n` elements, racing across
  multiple branches
- **THEN** the composed output contains exactly `(source length - n)`
  elements in total across all branches, never fewer

#### Scenario: Parallel skip() state resets per composition
- **WHEN** a stream chain containing `.skip(n)` is composed and consumed
  once under `RACING` execution, and then the same chain is composed again
  against a new source
- **THEN** the second composition's shared drop-count starts fresh,
  independent of what any branch observed during the first composition

#### Scenario: Ordered parallel skip() drops the first n in encounter order
- **WHEN** a stream chain containing an operation of variable per-element cost
  followed by `.skip(n)` is run under `RACING` execution on a pipeline that
  carries an encounter-order requirement at the `skip()`
- **THEN** the elements dropped are exactly the first `n` in the source's
  encounter order, the same ones the sequential pipeline drops

#### Scenario: Unordered parallel skip() drops the first n to arrive
- **WHEN** the same chain is run with `.unordered()` queued before the `.skip(n)`
- **THEN** exactly `n` elements are still dropped in total, but they need not be
  the first `n` in source order
