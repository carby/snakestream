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
- **WHEN** a chain is composed under the sequential executor versus under the fork-join executor
- **THEN** both leave `self._chain` unmutated, following the same contract

#### Scenario: Chain entries are not mutated by composition
- **WHEN** a chain containing a stateful operation (`distinct()`, `limit(n)`, `skip(n)`) is composed and consumed
- **THEN** the operation object stored in `self._chain` holds no per-composition state afterwards, and a subsequent composition builds a fresh sink from it

#### Scenario: The chain list handed to a driving loop is left intact
- **WHEN** the fork-join executor composes one chain into several batches, each dispatched over the same list of operation objects
- **THEN** that list is the same length and holds the same operation objects after every batch has run as it did before

### Requirement: Parallel distinct() and limit() remain globally correct across branches
Under the fork-join executor, the `distinct()` and `limit()` steps SHALL produce results that are globally correct across all batches within a single composition: `distinct()` SHALL NOT yield the same element from two different batches, and `limit(n)` SHALL NOT yield more than `n` elements in total across all batches combined. This holds even though state is freshly initialized per composition (per the sequential requirement above applied at the composition level), by sharing one state instance across every sink built for a given operation within that composition.

The fork-join executor SHALL build one state map per composition and pass that same map into every batch's `begin()`, so every sink built for a given operation across every batch of a composition shares one state instance.

Each batch runs its own chain, including its own instance of every sink, on its own OS thread (`asyncio.to_thread`) rather than as one more coroutine cooperatively scheduled on a single event loop. A count-then-increment or check-then-add against shared state is therefore a genuine data race between concurrently-running batches, not merely a hazard the old cooperative-scheduling model happened to avoid for free. `distinct()`'s shared state SHALL be a set guarded by a real lock (`_GuardedSet`, exposing `add_if_absent()` as one atomic operation) rather than a bare `set`, and `limit()`'s (and `skip()`'s, below) SHALL be a counter guarded by a real lock (`_GuardedCounter`) rather than a bare integer, so that the check-and-mutate stays atomic across threads and not only across `await` points on one event loop.

These guarantees SHALL hold for every operation in the chain a terminal executes under the fork-join executor, including operations declared before the `.parallel()` call that selected it. Because the executor governs the whole pipeline rather than only the portion declared after the switch, strictly more chains reach this requirement than before; the mechanism is unchanged.

**Which** elements survive is a separate question from **how many**, and is settled by whether the pipeline carries an encounter-order requirement at that operation's position (see the `racing-encounter-order` capability). Where it does, `limit(n)` yields the first `n` in encounter order and `distinct()` keeps the earliest-encountered member of each equal group. Where it does not — the pipeline was declared `unordered()` — `limit(n)` yields the first `n` to arrive across all batches in whatever order they complete, and `distinct()` keeps an arbitrary representative. The cardinality guarantees in this requirement hold identically in both cases; only the selection differs.

`limit(n)`'s check-and-reserve against the shared count SHALL be atomic with respect to every batch: no other batch's thread SHALL be able to observe or mutate the count between one batch's check and its reservation. This applies wherever a count is shared across batches; where the pipeline is ordered and the operation therefore runs in the single ordered pass ahead of the barrier rather than dispatched across concurrent batches, the requirement is satisfied trivially.

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
