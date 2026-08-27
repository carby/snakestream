## MODIFIED Requirements

### Requirement: Chain is not consumed by composition
Composing a stream's queued chain of intermediate operations into an executable pipeline (the executor's element-producing operation, and the `_wrap_sink()` helper it uses) SHALL NOT mutate or drain `self._chain`. The chain SHALL remain intact and usable for a subsequent composition after a prior composition has been fully or partially consumed.

The entries in `self._chain` SHALL be stateless operation objects, reusable across compositions; the stateful sinks that execute them SHALL be constructed fresh per composition. Composition SHALL NOT mutate any entry in the chain.

Because composition never mutates the chain, it SHALL NOT be necessary to defensively copy `self._chain` before handing it to a driving loop; the guarantee rests on the loop not mutating it, not on the caller copying it.

#### Scenario: Second terminal operation after full consumption
- **WHEN** a terminal operation (e.g. `collect()`) is called on a `Stream` and its result is fully consumed, and then a second terminal operation is called on the same `Stream` instance
- **THEN** the second call composes against the same chain of intermediate operations as the first call, rather than against an empty or partially-emptied chain

#### Scenario: Chain length unaffected by composition
- **WHEN** a `Stream` has one or more intermediate operations queued and the executor's element-producing operation is invoked any number of times (directly, or via `iterator()`, or via a terminal operation)
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

### Requirement: Building a composed pipeline does not recurse per chained operation

The executor's element-producing operation (and the `_wrap_sink()` helper it uses to link the sink chain) SHALL build the executable pipeline without recursing once per queued intermediate operation. Building (as opposed to consuming) a chain of intermediate operations SHALL NOT fail with `RecursionError` regardless of how many operations are queued, up to ordinary Python list-size limits.

Note: this requirement covers only the build-time traversal that links the sink chain. It does not cover recursion that occurs while *consuming* the composed pipeline: each intermediate sink's `accept()` calls `downstream.accept()`, so pushing one element through a chain of *k* operations is O(k) stack-deep. That is a separate concern, not addressed by this requirement, and is unchanged by the push-based redesign — the same O(k) per-element depth existed under the previous `async for`/`__anext__()` delegation model, and Java's own `Sink.ChainedReference` has it too.

#### Scenario: A long chain of intermediate operations builds successfully

- **WHEN** the sink-chain linking helper is called with a long list of queued operations (deep enough that a per-op-recursive implementation would approach Python's default recursion limit)
- **THEN** linking the sink chain completes without raising `RecursionError`
