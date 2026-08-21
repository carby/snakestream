## MODIFIED Requirements

### Requirement: Chain is not consumed by composition
Composing a stream's queued chain of intermediate operations into an executable pipeline (the executor's element-producing operation, and the `_wrap_sink()` helper it uses) SHALL NOT mutate or drain `self._chain`. The chain SHALL remain intact and usable for a subsequent composition after a prior composition has been fully or partially consumed.

The entries in `self._chain` SHALL be stateless operation objects, reusable across compositions; the stateful sinks that execute them SHALL be constructed fresh per composition. Composition SHALL NOT mutate any entry in the chain.

Because composition never mutates the chain, it SHALL NOT be necessary to defensively copy `self._chain` before handing it to a driving loop; the guarantee rests on the loop not mutating it, not on the caller copying it.

#### Scenario: Second terminal operation after full consumption
- **WHEN** a terminal operation (e.g. `collect()`) is called on a `Stream` and its result is fully consumed, and then a second terminal operation is called on the same `Stream` instance
- **THEN** the second call composes against the same chain of intermediate operations as the first call, rather than against an empty or partially-emptied chain

#### Scenario: Chain length unaffected by composition
- **WHEN** a `Stream` has one or more intermediate operations queued and `_compose()` is called any number of times
- **THEN** `len(self._chain)` after each call equals `len(self._chain)` before that call

#### Scenario: Sequential and parallel composition behave consistently
- **WHEN** a chain is composed under the sequential executor versus under the racing executor
- **THEN** both leave `self._chain` unmutated, following the same contract

#### Scenario: Chain entries are not mutated by composition
- **WHEN** a chain containing a stateful operation (`distinct()`, `limit(n)`, `skip(n)`) is composed and consumed
- **THEN** the operation object stored in `self._chain` holds no per-composition state afterwards, and a subsequent composition builds a fresh sink from it

#### Scenario: The chain list handed to a driving loop is left intact
- **WHEN** the racing executor composes one chain into several racing branches, each driven over the same list of operation objects
- **THEN** that list is the same length and holds the same operation objects after every branch has run as it did before

### Requirement: Stateful sequential closures reset per composition
Under the sequential executor, the internal state used by `distinct()` (the set of seen elements) and `limit()` (the count of elements accepted so far) SHALL be freshly initialized at the start of each composition, not shared across separate compositions of the same chain.

This SHALL be delivered through the sink protocol's `begin(state_map)` call: each composition SHALL build a fresh state map, so each composition's sinks begin from fresh state.

#### Scenario: distinct() does not leak state across compositions
- **WHEN** a `Stream` chain containing `.distinct()` is composed and consumed once, yielding its distinct elements, and then the same chain is composed again against a new source
- **THEN** the second composition's `distinct()` step evaluates distinctness only against elements seen during the second composition, not elements seen during the first

#### Scenario: limit() does not leak state across compositions
- **WHEN** a `Stream` chain containing `.limit(n)` is composed and consumed once, yielding up to `n` elements, and then the same chain is composed again against a new source
- **THEN** the second composition's `limit(n)` step allows up to `n` elements again, not zero

### Requirement: Parallel distinct() and limit() remain globally correct across branches
Under the racing executor, the `distinct()` and `limit()` steps SHALL produce results that are globally correct across all racing branches within a single composition: `distinct()` SHALL NOT yield the same element from two different branches, and `limit(n)` SHALL NOT yield more than `n` elements in total across all branches combined. This holds even though state is freshly initialized per composition (per the sequential requirement above applied at the composition level), by sharing one state instance across all branches of a given composition.

The racing executor SHALL build one state map per composition and pass that same map into every branch's `begin()`, so each branch's sinks for a given operation share one state instance.

These guarantees SHALL hold for every operation in the chain a terminal executes under the racing executor, including operations declared before the `.parallel()` call that selected it. Because the executor governs the whole pipeline rather than only the portion declared after the switch, strictly more chains reach this requirement than before; the mechanism is unchanged.

`limit(n)`'s check-and-reserve against the shared count SHALL be atomic with respect to racing branches: no suspension point SHALL occur between observing the count and reserving a slot.

When the driving loop stops pulling because cancellation was requested and closes the shared upstream source, that closure SHALL be safe with respect to any other branch subsequently pulling from or closing the same shared source: no unhandled exception SHALL escape the racing executor's task loop as a result.

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
