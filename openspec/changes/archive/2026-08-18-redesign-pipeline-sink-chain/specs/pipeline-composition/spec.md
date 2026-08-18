## MODIFIED Requirements

### Requirement: Chain is not consumed by composition
Composing a stream's queued chain of intermediate operations into an executable pipeline (`BaseStream._compose()`, and the `_sequential()`/`_parallel()` helpers it uses) SHALL NOT mutate or drain `self._chain`. The chain SHALL remain intact and usable for a subsequent composition after a prior composition has been fully or partially consumed.

The entries in `self._chain` SHALL be stateless operation objects, reusable across compositions; the stateful sinks that execute them SHALL be constructed fresh per composition. Composition SHALL NOT mutate any entry in the chain.

#### Scenario: Second terminal operation after full consumption
- **WHEN** a terminal operation (e.g. `collect()`) is called on a `Stream` and its result is fully consumed, and then a second terminal operation is called on the same `Stream` instance
- **THEN** the second call composes against the same chain of intermediate operations as the first call, rather than against an empty or partially-emptied chain

#### Scenario: Chain length unaffected by composition
- **WHEN** a `Stream` has one or more intermediate operations queued and `_compose()` is called any number of times
- **THEN** `len(self._chain)` after each call equals `len(self._chain)` before that call

#### Scenario: Sequential and parallel composition behave consistently
- **WHEN** a chain is composed via `Stream._compose()` (sequential) versus `ParallelStream._compose()` (parallel)
- **THEN** both leave `self._chain` unmutated, following the same contract

#### Scenario: Chain entries are not mutated by composition
- **WHEN** a chain containing a stateful operation (`distinct()`, `limit(n)`, `skip(n)`) is composed and consumed
- **THEN** the operation object stored in `self._chain` holds no per-composition state afterwards, and a subsequent composition builds a fresh sink from it

### Requirement: Stateful sequential closures reset per composition
For `Stream` (sequential, non-parallel) pipelines, the internal state used by `distinct()` (the set of seen elements) and `limit()` (the count of elements accepted so far) SHALL be freshly initialized at the start of each composition, not shared across separate compositions of the same chain.

This SHALL be delivered through the sink protocol's `begin(state_map)` call: `Stream._compose()` SHALL build a fresh state map for each composition, so each composition's sinks begin from fresh state.

#### Scenario: distinct() does not leak state across compositions
- **WHEN** a `Stream` chain containing `.distinct()` is composed and consumed once, yielding its distinct elements, and then the same chain is composed again against a new source
- **THEN** the second composition's `distinct()` step evaluates distinctness only against elements seen during the second composition, not elements seen during the first

#### Scenario: limit() does not leak state across compositions
- **WHEN** a `Stream` chain containing `.limit(n)` is composed and consumed once, yielding up to `n` elements, and then the same chain is composed again against a new source
- **THEN** the second composition's `limit(n)` step allows up to `n` elements again, not zero

### Requirement: Parallel distinct() and limit() remain globally correct across branches
For `ParallelStream` pipelines, the `distinct()` and `limit()` steps SHALL produce results that are globally correct across all racing branches within a single composition: `distinct()` SHALL NOT yield the same element from two different branches, and `limit(n)` SHALL NOT yield more than `n` elements in total across all branches combined. This holds even though state is freshly initialized per composition (per the sequential requirement above applied at the composition level), by sharing one state instance across all branches of a given composition.

`ParallelStream._parallel()` SHALL build one state map per composition and pass that same map into every branch's `begin()`, so each branch's sinks for a given operation share one state instance.

`limit(n)`'s check-and-reserve against the shared count SHALL be atomic with respect to racing branches: no suspension point SHALL occur between observing the count and reserving a slot.

When the driving loop stops pulling because cancellation was requested and closes the shared upstream source, that closure SHALL be safe with respect to any other branch subsequently pulling from or closing the same shared source: no unhandled exception SHALL escape `ParallelStream._parallel()`'s task loop as a result.

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
`Stream.limit(n)` SHALL cause at most `n` elements to be pulled from the upstream source. An `(n+1)`th element SHALL NOT be pulled in order to discover that the limit has been reached.

This SHALL be delivered through the sink protocol's cancellation mechanism rather than by the operation closing its own upstream: `limit(n)`'s sink SHALL report `cancellation_requested()` as `True` once it has accepted `n` elements, and the loop driving the composed chain SHALL check that report after each `accept()` and stop pulling before issuing another pull. Closing the source SHALL be the responsibility of the driving loop, not of `limit()` itself.

#### Scenario: limit() does not pull past the nth element
- **WHEN** a `Stream` chain containing `.peek(fn).limit(n)` is composed and consumed against a source with more than `n` elements
- **THEN** `fn` is called exactly `n` times, not `n + 1` times

#### Scenario: limit() on an exactly-sized source still terminates cleanly
- **WHEN** a `Stream` chain containing `.limit(n)` is composed against a source with exactly `n` elements
- **THEN** the composed output contains all `n` elements and terminates without error

#### Scenario: limit() on a shorter-than-n source yields only what's available
- **WHEN** a `Stream` chain containing `.limit(n)` is composed against a source with fewer than `n` elements
- **THEN** the composed output contains all of the source's elements and terminates without error, without attempting to pull past exhaustion

#### Scenario: The source is closed when limit() short-circuits
- **WHEN** a `Stream` chain containing `.limit(n)` stops early because the limit was reached
- **THEN** the upstream source generator is closed by the driving loop

### Requirement: Stateful sequential skip() closures reset per composition
For `Stream` (sequential, non-parallel) pipelines, the internal state used by `skip()` (the count of elements dropped so far) SHALL be freshly initialized at the start of each composition, not shared across separate compositions of the same chain, following the same per-composition reset contract already established for `distinct()`/`limit()`, and delivered through the same `begin(state_map)` call.

#### Scenario: skip() does not leak state across compositions
- **WHEN** a `Stream` chain containing `.skip(n)` is composed and consumed
  once, dropping the first `n` elements, and then the same chain is composed
  again against a new source
- **THEN** the second composition's `skip(n)` step drops up to `n` elements
  again, not zero

### Requirement: Building a composed pipeline does not recurse per chained operation

`BaseStream._compose()` (and the `_sequential()` helper it uses for sequential composition) SHALL build the executable pipeline without recursing once per queued intermediate operation. Building (as opposed to consuming) a chain of intermediate operations SHALL NOT fail with `RecursionError` regardless of how many operations are queued, up to ordinary Python list-size limits.

Note: this requirement covers only the build-time traversal that links the sink chain. It does not cover recursion that occurs while *consuming* the composed pipeline: each intermediate sink's `accept()` calls `downstream.accept()`, so pushing one element through a chain of *k* operations is O(k) stack-deep. That is a separate concern, not addressed by this requirement, and is unchanged by the push-based redesign — the same O(k) per-element depth existed under the previous `async for`/`__anext__()` delegation model, and Java's own `Sink.ChainedReference` has it too.

#### Scenario: A long chain of intermediate operations builds successfully

- **WHEN** `BaseStream._sequential()` is called with a long list of queued operations (deep enough that a per-op-recursive implementation would approach Python's default recursion limit)
- **THEN** linking the sink chain completes without raising `RecursionError`

### Requirement: flat_map() closes its per-element inner generator on early termination

`Stream.flat_map()`'s sink SHALL explicitly close the inner stream's composed generator for the outer element currently being processed, whether that inner generator is exhausted normally, raises, or is abandoned mid-iteration because downstream requested cancellation or the pipeline was torn down early (e.g. a downstream `.limit()`). The inner stream SHALL be iterated through its own composition directly rather than through a `collect(to_generator)` wrapper, so there is a single generator layer to close.

#### Scenario: Inner generator is closed when the outer chain short-circuits

- **WHEN** a chain `.flat_map(mapper).limit(n)` is composed and consumed, where `mapper(i)` for some outer element produces a tracked inner generator with `finally:` cleanup, and consumption stops (via `limit(n)`) while that inner generator is mid-iteration
- **THEN** the abandoned inner generator's `finally:` cleanup runs (i.e. `aclose()` was called on it)

#### Scenario: Inner generator is still closed on normal exhaustion

- **WHEN** a chain `.flat_map(mapper)` is composed and consumed to completion
- **THEN** every inner generator produced by `mapper(i)` for each outer element has been closed (either by natural exhaustion or explicit `aclose()`), with no change to the elements yielded compared to before this change
