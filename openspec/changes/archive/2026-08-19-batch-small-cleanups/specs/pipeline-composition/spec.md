## MODIFIED Requirements

### Requirement: Chain is not consumed by composition
Composing a stream's queued chain of intermediate operations into an executable pipeline (`BaseStream._compose()`, and the `_wrap_sink()`/`_parallel()` helpers it uses) SHALL NOT mutate or drain `self._chain`. The chain SHALL remain intact and usable for a subsequent composition after a prior composition has been fully or partially consumed.

The entries in `self._chain` SHALL be stateless operation objects, reusable across compositions; the stateful sinks that execute them SHALL be constructed fresh per composition. Composition SHALL NOT mutate any entry in the chain.

Because composition never mutates the chain, it SHALL NOT be necessary to defensively copy `self._chain` before handing it to a driving loop; the guarantee rests on the loop not mutating it, not on the caller copying it.

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

#### Scenario: The chain list handed to a driving loop is left intact
- **WHEN** a `ParallelStream` composes one chain into several racing branches, each driven over the same list of operation objects
- **THEN** that list is the same length and holds the same operation objects after every branch has run as it did before

### Requirement: limit() short-circuits without over-pulling upstream
`Stream.limit(n)` SHALL cause at most `n` elements to be pulled from the upstream source. An `(n+1)`th element SHALL NOT be pulled in order to discover that the limit has been reached.

This SHALL be delivered through the sink protocol's cancellation mechanism rather than by the operation closing its own upstream: `limit(n)`'s sink SHALL report `cancellation_requested()` as `True` once it has accepted `n` elements, and the loop driving the composed chain SHALL check that report after each `accept()` and stop pulling before issuing another pull. Closing the source SHALL be the responsibility of the driving loop, not of `limit()` itself.

The guarantee SHALL hold for `n = 0` as well: `limit(0)` is cancelled before the composed pipeline has seen any element, so **no** element SHALL be pulled from the source and no upstream operation's per-element side effect (a `peek()` consumer, a `map()` mapper) SHALL run. This requires the driving loop to check cancellation before its first pull, not only after each `accept()`.

The same no-over-pull guarantee SHALL hold when the cancellation originates at a **terminal** sink rather than at a mid-chain `limit()`: a driving loop that pushes into a terminal SHALL check the head sink's `cancellation_requested()` after each `accept()` and stop pulling before issuing another pull, and SHALL close the source on that early exit.

#### Scenario: limit() does not pull past the nth element
- **WHEN** a `Stream` chain containing `.peek(fn).limit(n)` is composed and consumed against a source with more than `n` elements
- **THEN** `fn` is called exactly `n` times, not `n + 1` times

#### Scenario: limit(0) pulls nothing at all
- **WHEN** a `Stream` chain containing `.peek(fn).limit(0)` is composed and consumed against a non-empty source
- **THEN** the composed output is empty, `fn` is never called, and no element is pulled from the source

#### Scenario: limit() on an exactly-sized source still terminates cleanly
- **WHEN** a `Stream` chain containing `.limit(n)` is composed against a source with exactly `n` elements
- **THEN** the composed output contains all `n` elements and terminates without error

#### Scenario: limit() on a shorter-than-n source yields only what's available
- **WHEN** a `Stream` chain containing `.limit(n)` is composed against a source with fewer than `n` elements
- **THEN** the composed output contains all of the source's elements and terminates without error, without attempting to pull past exhaustion

#### Scenario: The source is closed when limit() short-circuits
- **WHEN** a `Stream` chain containing `.limit(n)` stops early because the limit was reached
- **THEN** the upstream source generator is closed by the driving loop

#### Scenario: A short-circuiting terminal does not over-pull either
- **WHEN** a chain `.peek(fn).any_match(predicate)` is driven against a source with more than one element and the first element satisfies `predicate`
- **THEN** `fn` is called exactly once, and the upstream source generator is closed by the driving loop

### Requirement: Building a composed pipeline does not recurse per chained operation

`BaseStream._compose()` (and the `_wrap_sink()` helper it uses to link the sink chain) SHALL build the executable pipeline without recursing once per queued intermediate operation. Building (as opposed to consuming) a chain of intermediate operations SHALL NOT fail with `RecursionError` regardless of how many operations are queued, up to ordinary Python list-size limits.

Note: this requirement covers only the build-time traversal that links the sink chain. It does not cover recursion that occurs while *consuming* the composed pipeline: each intermediate sink's `accept()` calls `downstream.accept()`, so pushing one element through a chain of *k* operations is O(k) stack-deep. That is a separate concern, not addressed by this requirement, and is unchanged by the push-based redesign — the same O(k) per-element depth existed under the previous `async for`/`__anext__()` delegation model, and Java's own `Sink.ChainedReference` has it too.

#### Scenario: A long chain of intermediate operations builds successfully

- **WHEN** the sink-chain linking helper is called with a long list of queued operations (deep enough that a per-op-recursive implementation would approach Python's default recursion limit)
- **THEN** linking the sink chain completes without raising `RecursionError`
