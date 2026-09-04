## Purpose

Defines the contract for turning a `Stream`'s queued chain of intermediate-operation closures into an executable pipeline via the executor's element-producing operation (and the `_wrap_sink()` helper it uses). Covers two guarantees: that composing a chain never consumes or mutates it, so a stream can be composed and re-composed across multiple terminal operations; and that stateful intermediate operations (`distinct()`, `limit()`) start with fresh state on each composition rather than leaking state from a prior run, under both the sequential executor and the fork-join executor (where state must additionally stay globally correct across the concurrently-running batches of one composition).

## Requirements

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
- **WHEN** a chain is composed under the sequential executor versus under the fork-join executor
- **THEN** both leave `self._chain` unmutated, following the same contract

#### Scenario: Chain entries are not mutated by composition
- **WHEN** a chain containing a stateful operation (`distinct()`, `limit(n)`, `skip(n)`) is composed and consumed
- **THEN** the operation object stored in `self._chain` holds no per-composition state afterwards, and a subsequent composition builds a fresh sink from it

#### Scenario: The chain list handed to a driving loop is left intact
- **WHEN** the fork-join executor composes one chain into several batches, each dispatched over the same list of operation objects
- **THEN** that list is the same length and holds the same operation objects after every batch has run as it did before

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
Under the fork-join executor, the `distinct()` and `limit()` steps SHALL produce results that are globally correct across all batches within a single composition: `distinct()` SHALL NOT yield the same element from two different batches, and `limit(n)` SHALL NOT yield more than `n` elements in total across all batches combined. This holds even though state is freshly initialized per composition (per the sequential requirement above applied at the composition level), by sharing one state instance across every sink built for a given operation within that composition.

The fork-join executor SHALL build one state map per composition and pass that same map into every batch's `begin()`, so every sink built for a given operation across every batch of a composition shares one state instance.

Each batch runs its own chain, including its own instance of every sink, on its own OS thread (`asyncio.to_thread`) rather than as one more coroutine cooperatively scheduled on a single event loop. A count-then-increment or check-then-add against shared state is therefore a genuine data race between concurrently-running batches, not merely a hazard the old cooperative-scheduling model happened to avoid for free. `distinct()`'s shared state SHALL be a set guarded by a real lock (`_GuardedSet`, exposing `add_if_absent()` as one atomic operation) rather than a bare `set`, and `limit()`'s (and `skip()`'s, below) SHALL be a counter guarded by a real lock (`_GuardedCounter`) rather than a bare integer, so that the check-and-mutate stays atomic across threads and not only across `await` points on one event loop.

These guarantees SHALL hold for every operation in the chain a terminal executes under the fork-join executor, including operations declared before the `.parallel()` call that selected it. Because the executor governs the whole pipeline rather than only the portion declared after the switch, strictly more chains reach this requirement than before; the mechanism is unchanged.

**Which** elements survive is a separate question from **how many**, and is settled by whether the pipeline carries an encounter-order requirement at that operation's position (see the `racing-encounter-order` capability). Where it does, `limit(n)` yields the first `n` in encounter order and `distinct()` keeps the earliest-encountered member of each equal group. Where it does not — the pipeline was declared `unordered()` — `limit(n)` yields the first `n` to arrive across all batches in whatever order they complete, and `distinct()` keeps an arbitrary representative. The cardinality guarantees in this requirement hold identically in both cases; only the selection differs.

`limit(n)`'s check-and-reserve against the shared count SHALL be atomic with respect to every batch: no other batch's thread SHALL be able to observe or mutate the count between one batch's check and its reservation. This applies wherever a count is shared across batches; where the pipeline is ordered and the operation is therefore not dispatched across concurrent batches, the requirement is satisfied trivially.

When the driving loop stops pulling because cancellation was requested and closes the shared upstream source, that closure SHALL be safe with respect to any other in-flight batch subsequently pulling from or closing the same shared source: no unhandled exception SHALL escape the fork-join executor's dispatch loop as a result. This SHALL hold whether the cancelling operation sits inside a batch or downstream of an ordering barrier: cancellation raised downstream SHALL still reach and stop the upstream pull.

#### Scenario: Parallel distinct() does not yield cross-branch duplicates
- **WHEN** a chain containing `.distinct()` is composed under the fork-join executor against a source containing a repeated element, and multiple batches may each encounter that element
- **THEN** the composed output contains that element exactly once in total across all batches

#### Scenario: Parallel limit() does not exceed n in total
- **WHEN** a chain containing `.limit(n)` is composed under the fork-join executor against a source with more than `n` elements, dispatched across multiple batches
- **THEN** the composed output contains at most `n` elements in total across all batches

#### Scenario: Parallel state resets per composition
- **WHEN** a chain containing `.distinct()` or `.limit(n)` is composed under the fork-join executor and consumed once, and then the same chain is composed again against a new source
- **THEN** the second composition's shared state starts fresh, independent of what any batch observed during the first composition

#### Scenario: A second branch pulling from a closed shared source terminates cleanly
- **WHEN** a chain containing `.limit(n)` is composed under the fork-join executor and one batch closes the shared upstream source after the shared count reaches `n`, and another in-flight batch subsequently calls `__anext__()` on that same shared source
- **THEN** that batch's pull ends its local iteration (as a normal end-of-stream, not an unhandled exception) rather than propagating an error out of the fork-join executor

#### Scenario: A stateful op declared before .parallel() is still globally correct
- **WHEN** `.distinct()` is declared before `.parallel()` in a chain, so that it now runs under the fork-join executor
- **THEN** it yields each distinct element exactly once in total across all batches, exactly as it does when declared after the switch

#### Scenario: The cardinality guarantee holds on an ordered pipeline too
- **WHEN** a chain containing `.limit(n)` or `.distinct()` is composed under the fork-join executor on a pipeline that carries an encounter-order requirement at that operation's position
- **THEN** `limit(n)` still yields at most `n` elements in total and `distinct()` still yields each distinct element exactly once, with the selection determined by encounter order

#### Scenario: Concurrent batches contending on shared state stay correct under real thread concurrency
- **WHEN** a large source is run under `.parallel().unordered()` with `.limit(n)`, `.skip(n)` and `.distinct()`, dispatched across many concurrently-running batches on the free-threaded build
- **THEN** the cardinality guarantees above hold exactly, repeatably, across many trials — not only "usually", which is what a missing lock would produce

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
Under the fork-join executor, the `skip()` step SHALL drop exactly `n` elements
across all batches combined, not up to `n` elements per batch, guarded by the
same `_GuardedCounter` lock described above for `limit()`.

**Which** `n` are dropped depends on whether the pipeline carries an
encounter-order requirement at that operation's position (see the
`racing-encounter-order` capability). Where it does, `skip(n)` SHALL drop the
first `n` elements in encounter order, matching the sequential result. Where it
does not — the pipeline was declared `unordered()` — "first `n`" means the first
`n` elements pulled across all batches in whatever order they complete, which
need not be the first `n` in source order.

The total-count guarantee is the same in both cases: exactly `n` elements are
dropped when the source has at least `n`, and the whole source is dropped when
it has fewer.

#### Scenario: Parallel skip() does not exceed n dropped in total
- **WHEN** a stream chain containing `.skip(n)` is run under the fork-join
  executor against a source with more than `n` elements, dispatched across
  multiple batches
- **THEN** the composed output contains exactly `(source length - n)`
  elements in total across all batches, never fewer

#### Scenario: Parallel skip() state resets per composition
- **WHEN** a stream chain containing `.skip(n)` is composed and consumed
  once under the fork-join executor, and then the same chain is composed again
  against a new source
- **THEN** the second composition's shared drop-count starts fresh,
  independent of what any batch observed during the first composition

#### Scenario: Ordered parallel skip() drops the first n in encounter order
- **WHEN** a stream chain containing an operation of variable per-element cost
  followed by `.skip(n)` is run under the fork-join executor on a pipeline that
  carries an encounter-order requirement at the `skip()`
- **THEN** the elements dropped are exactly the first `n` in the source's
  encounter order, the same ones the sequential pipeline drops

#### Scenario: Unordered parallel skip() drops the first n to arrive
- **WHEN** the same chain is run with `.unordered()` queued before the `.skip(n)`
- **THEN** exactly `n` elements are still dropped in total, but they need not be
  the first `n` in source order

### Requirement: Parallel branches serialize pulls from the shared upstream source

The fork-join executor SHALL NOT call `__anext__()` on the shared upstream
source from more than one place at a time. This SHALL hold by construction
rather than by a lock guarding concurrent access: the executor obtains a single
iterator from the raw source (`aiter(source)`, once, before any batch is
dispatched) and pulls each batch's elements from it in one sequential loop; a
batch's own per-element chain only begins running, on its own thread, once its
elements have already been pulled. There is therefore never a point at which
two threads are calling `__anext__()` on the shared source concurrently — the
pulling and the concurrent processing are different phases, not different
threads racing the same call.

Each batch's own downstream processing (the intermediate-operation chain
applied to the elements already pulled for that batch) SHALL still run
concurrently with other batches' processing and with the next round's pulls.

#### Scenario: A source with a real await suspension point does not raise

- **WHEN** a stream is run under the fork-join executor over a source whose `__anext__()` contains a genuine `await` suspension point (e.g. `await asyncio.sleep(0)`), and any chain of intermediate operations is composed and consumed
- **THEN** no `RuntimeError: anext(): asynchronous generator is already running` is raised, and all elements the source produces are yielded exactly once in total across all batches

#### Scenario: Downstream processing remains concurrent across branches

- **WHEN** a stream chain containing a `map()` step with an `await`-based mapper is run under the fork-join executor against a source with multiple elements
- **THEN** more than one batch's mapper invocations may be in flight concurrently, even though every pull from the shared upstream source happened in one sequential loop before any of those batches was dispatched

#### Scenario: One branch closing the shared source remains safe for other branches

- **WHEN** a stream chain containing `.limit(n)` is run under the fork-join executor against a source with a real `await` suspension point, and one batch closes the shared upstream source after the shared count reaches `n`
- **THEN** any other in-flight batch subsequently pulling from or closing that same shared source ends its local iteration cleanly (normal end-of-stream), without an unhandled exception escaping the fork-join executor's dispatch loop

### Requirement: Building a composed pipeline does not recurse per chained operation

The executor's element-producing operation (and the `_wrap_sink()` helper it uses to link the sink chain) SHALL build the executable pipeline without recursing once per queued intermediate operation. Building (as opposed to consuming) a chain of intermediate operations SHALL NOT fail with `RecursionError` regardless of how many operations are queued, up to ordinary Python list-size limits.

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
