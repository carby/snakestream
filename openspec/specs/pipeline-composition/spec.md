## Purpose

Defines the contract for turning a `Stream`'s queued chain of intermediate-operation closures into an executable pipeline via `_compose()` (and the `_wrap_sink()`/`_parallel()` helpers it uses). Covers two guarantees: that composing a chain never consumes or mutates it, so a stream can be composed and re-composed across multiple terminal operations; and that stateful intermediate operations (`distinct()`, `limit()`) start with fresh state on each composition rather than leaking state from a prior run, under both `SEQUENTIAL` execution and `RACING` execution (where state must additionally stay globally correct across racing branches within one composition).

## Requirements

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

### Requirement: skip() drops the first n elements
`Stream.skip(n)` SHALL drop the first `n` elements pulled from its upstream
source and yield every element after that. If the upstream source has fewer
than `n` elements, `skip(n)` SHALL drain the source and yield nothing.

#### Scenario: skip() drops the first n elements of a longer source
- **WHEN** a `Stream` chain containing `.skip(n)` is composed and consumed
  against a source with more than `n` elements
- **THEN** the composed output omits the first `n` elements pulled from the
  source and contains every element after them, in order

#### Scenario: skip() on a source with fewer than n elements yields nothing
- **WHEN** a `Stream` chain containing `.skip(n)` is composed and consumed
  against a source with fewer than `n` elements
- **THEN** the composed output is empty

#### Scenario: skip(0) is a no-op
- **WHEN** a `Stream` chain containing `.skip(0)` is composed and consumed
- **THEN** the composed output is identical to the same chain without
  `.skip(0)`

### Requirement: Stateful sequential skip() closures reset per composition
For `Stream` (sequential, non-parallel) pipelines, the internal state used by `skip()` (the count of elements dropped so far) SHALL be freshly initialized at the start of each composition, not shared across separate compositions of the same chain, following the same per-composition reset contract already established for `distinct()`/`limit()`, and delivered through the same `begin(state_map)` call.

#### Scenario: skip() does not leak state across compositions
- **WHEN** a `Stream` chain containing `.skip(n)` is composed and consumed
  once, dropping the first `n` elements, and then the same chain is composed
  again against a new source
- **THEN** the second composition's `skip(n)` step drops up to `n` elements
  again, not zero

### Requirement: Parallel skip() remains globally correct across branches
Under `RACING` execution, the `skip()` step SHALL drop exactly the first `n`
elements pulled across all racing branches combined, not up to `n` elements
per branch. Because branches race independently, "first `n`" means the first
`n` elements pulled across all branches in whatever order the race resolves
them, not necessarily the first `n` elements in source order.

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

### Requirement: Parallel branches serialize pulls from the shared upstream source

`race_through()`'s racing branches SHALL NOT call `__anext__()` on the shared upstream source concurrently. Only one branch's pull from the shared source SHALL be in flight at any point in time; each branch's own downstream processing (the intermediate-operation closures applied after the pull) SHALL still be able to run concurrently with other branches' pulls and processing.

#### Scenario: A source with a real await suspension point does not raise

- **WHEN** a stream is run under `RACING` execution over a source whose `__anext__()` contains a genuine `await` suspension point (e.g. `await asyncio.sleep(0)`), and any chain of intermediate operations is composed and consumed
- **THEN** no `RuntimeError: anext(): asynchronous generator is already running` is raised, and all elements the source produces are yielded exactly once in total across all racing branches

#### Scenario: Downstream processing remains concurrent across branches

- **WHEN** a stream chain containing a `map()` step with an `await`-based mapper is run under `RACING` execution against a source with multiple elements
- **THEN** more than one branch's mapper invocation may be in flight concurrently, even though their pulls from the shared upstream source are serialized

#### Scenario: One branch closing the shared source remains safe for other branches

- **WHEN** a stream chain containing `.limit(n)` is run under `RACING` execution against a source with a real `await` suspension point, and racing branch A closes the shared upstream source after the shared count reaches `n`
- **THEN** any other branch subsequently pulling from or closing that same shared source ends its local iteration cleanly (normal end-of-stream), without an unhandled exception escaping `race_through()`'s task loop

### Requirement: Building a composed pipeline does not recurse per chained operation

`Stream._compose()` (and the `_wrap_sink()` helper it uses to link the sink chain) SHALL build the executable pipeline without recursing once per queued intermediate operation. Building (as opposed to consuming) a chain of intermediate operations SHALL NOT fail with `RecursionError` regardless of how many operations are queued, up to ordinary Python list-size limits.

Note: this requirement covers only the build-time traversal that links the sink chain. It does not cover recursion that occurs while *consuming* the composed pipeline: each intermediate sink's `accept()` calls `downstream.accept()`, so pushing one element through a chain of *k* operations is O(k) stack-deep. That is a separate concern, not addressed by this requirement, and is unchanged by the push-based redesign — the same O(k) per-element depth existed under the previous `async for`/`__anext__()` delegation model, and Java's own `Sink.ChainedReference` has it too.

#### Scenario: A long chain of intermediate operations builds successfully

- **WHEN** the sink-chain linking helper is called with a long list of queued operations (deep enough that a per-op-recursive implementation would approach Python's default recursion limit)
- **THEN** linking the sink chain completes without raising `RecursionError`

### Requirement: flat_map() closes its per-element inner generator on early termination

`Stream.flat_map()`'s sink SHALL explicitly close the inner stream's composed generator for the outer element currently being processed, whether that inner generator is exhausted normally, raises, or is abandoned mid-iteration because downstream requested cancellation or the pipeline was torn down early (e.g. a downstream `.limit()`, or a short-circuiting terminal such as `any_match()` or `find_first()`). The inner stream SHALL be iterated through its own composition directly rather than through a `collect(to_generator)` wrapper, so there is a single generator layer to close.

`flat_map()`'s per-element inner loop SHALL stop as soon as downstream reports cancellation, regardless of whether that cancellation originated at a mid-chain `limit()` or at a terminal sink.

#### Scenario: Inner generator is closed when the outer chain short-circuits

- **WHEN** a chain `.flat_map(mapper).limit(n)` is composed and consumed, where `mapper(i)` for some outer element produces a tracked inner generator with `finally:` cleanup, and consumption stops (via `limit(n)`) while that inner generator is mid-iteration
- **THEN** the abandoned inner generator's `finally:` cleanup runs (i.e. `aclose()` was called on it)

#### Scenario: Inner generator is still closed on normal exhaustion

- **WHEN** a chain `.flat_map(mapper)` is composed and consumed to completion
- **THEN** every inner generator produced by `mapper(i)` for each outer element has been closed (either by natural exhaustion or explicit `aclose()`), with the elements yielded unaffected

#### Scenario: Inner iteration stops when a terminal short-circuits

- **WHEN** a chain `.flat_map(mapper).find_first()` is driven, and the first outer element's inner stream has several elements
- **THEN** exactly one element is taken from that inner stream, its generator is closed, and no further outer element is pulled
