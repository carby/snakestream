## Purpose

Defines the contract for turning a `BaseStream`'s queued chain of intermediate-operation closures into an executable pipeline via `_compose()` (and the `_sequential()`/`_parallel()` helpers it uses). Covers two guarantees: that composing a chain never consumes or mutates it, so a stream can be composed and re-composed across multiple terminal operations; and that stateful intermediate operations (`distinct()`, `limit()`) start with fresh state on each composition rather than leaking state from a prior run, in both `Stream` (sequential) and `ParallelStream` (parallel, where state must additionally stay globally correct across racing branches within one composition).

## Requirements

### Requirement: Chain is not consumed by composition
Composing a stream's queued intermediate-operation chain into an executable pipeline (`BaseStream._compose()`, and the `_sequential()`/`_parallel()` helpers it uses) SHALL NOT mutate or drain `self._chain`. The chain SHALL remain intact and usable for a subsequent composition after a prior composition has been fully or partially consumed.

#### Scenario: Second terminal operation after full consumption
- **WHEN** a terminal operation (e.g. `collect()`) is called on a `Stream` and its result is fully consumed, and then a second terminal operation is called on the same `Stream` instance
- **THEN** the second call composes against the same chain of intermediate operations as the first call, rather than against an empty or partially-emptied chain

#### Scenario: Chain length unaffected by composition
- **WHEN** a `Stream` has one or more intermediate operations queued and `_compose()` is called any number of times
- **THEN** `len(self._chain)` after each call equals `len(self._chain)` before that call

#### Scenario: Sequential and parallel composition behave consistently
- **WHEN** a chain is composed via `Stream._compose()` (sequential) versus `ParallelStream._compose()` (parallel)
- **THEN** both leave `self._chain` unmutated, following the same contract

### Requirement: Stateful sequential closures reset per composition
For `Stream` (sequential, non-parallel) pipelines, the internal state used by `distinct()` (the set of seen elements) and `limit()` (the count of elements yielded so far) SHALL be freshly initialized at the start of each composition, not shared across separate compositions of the same chain.

#### Scenario: distinct() does not leak state across compositions
- **WHEN** a `Stream` chain containing `.distinct()` is composed and consumed once, yielding its distinct elements, and then the same chain is composed again against a new source
- **THEN** the second composition's `distinct()` step evaluates distinctness only against elements seen during the second composition, not elements seen during the first

#### Scenario: limit() does not leak state across compositions
- **WHEN** a `Stream` chain containing `.limit(n)` is composed and consumed once, yielding up to `n` elements, and then the same chain is composed again against a new source
- **THEN** the second composition's `limit(n)` step allows up to `n` elements again, not zero

### Requirement: Parallel distinct() and limit() remain globally correct across branches
For `ParallelStream` pipelines, the `distinct()` and `limit()` steps SHALL produce results that are globally correct across all racing branches within a single composition: `distinct()` SHALL NOT yield the same element from two different branches, and `limit(n)` SHALL NOT yield more than `n` elements in total across all branches combined. This holds even though state is freshly initialized per composition (per the sequential requirement above applied at the composition level), by sharing one state instance across all branches of a given composition. When one branch observes the shared count reaching `n` and closes the shared upstream source, that closure SHALL be safe with respect to any other branch subsequently pulling from or closing the same shared source: no unhandled exception SHALL escape `ParallelStream._parallel()`'s task loop as a result.

#### Scenario: Parallel distinct() does not yield cross-branch duplicates
- **WHEN** a `ParallelStream` chain containing `.distinct()` is composed against a source containing a repeated element, and multiple racing branches may each encounter that element
- **THEN** the composed output contains that element exactly once in total across all branches

#### Scenario: Parallel limit() does not exceed n in total
- **WHEN** a `ParallelStream` chain containing `.limit(n)` is composed against a source with more than `n` elements, racing across multiple branches
- **THEN** the composed output contains at most `n` elements in total across all branches

#### Scenario: Parallel state resets per composition
- **WHEN** a `ParallelStream` chain containing `.distinct()` or `.limit(n)` is composed and consumed once, and then the same chain is composed again against a new source
- **THEN** the second composition's shared state starts fresh, independent of what any branch observed during the first composition

#### Scenario: A second branch pulling from a closed shared source terminates cleanly
- **WHEN** a `ParallelStream` chain containing `.limit(n)` is composed and racing branch A closes the shared upstream source after the shared count reaches `n`, and racing branch B subsequently calls `__anext__()` on that same shared source
- **THEN** branch B's pull ends its local iteration (as a normal end-of-stream, not an unhandled exception) rather than propagating an error out of `ParallelStream._parallel()`

### Requirement: limit() short-circuits without over-pulling upstream
`Stream.limit(n)` SHALL pull at most `n` elements from its upstream source. It SHALL NOT pull an `(n+1)`th element in order to discover that the limit has been reached; the decision to stop SHALL be made before pulling the next element, based on the count of elements already yielded.

#### Scenario: limit() does not pull past the nth element
- **WHEN** a `Stream` chain containing `.peek(fn).limit(n)` is composed and consumed against a source with more than `n` elements
- **THEN** `fn` is called exactly `n` times, not `n + 1` times

#### Scenario: limit() on an exactly-sized source still terminates cleanly
- **WHEN** a `Stream` chain containing `.limit(n)` is composed against a source with exactly `n` elements
- **THEN** the composed output contains all `n` elements and terminates without error

#### Scenario: limit() on a shorter-than-n source yields only what's available
- **WHEN** a `Stream` chain containing `.limit(n)` is composed against a source with fewer than `n` elements
- **THEN** the composed output contains all of the source's elements and terminates without error, without attempting to pull past exhaustion
