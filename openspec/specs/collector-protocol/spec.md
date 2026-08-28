## Purpose

Defines the `Collector` shape every `collectors.py` factory returns — a
supplier/accumulator/combiner/finisher quadruple mirroring Java's
`Collector<T,A,R>` — and how `Stream.collect()` accepts and drives one.

## Requirements

### Requirement: `Collector(supplier, accumulator, combiner, finisher)` public shape

The library SHALL expose a public `Collector` type constructed from four
callable parts, mirroring Java's `Collector<T,A,R>`:

- `supplier` — a no-argument callable returning a fresh accumulation
  container. It SHALL be called exactly once per collected stream, so no two
  collections ever share a container and a single `Collector` value is safe to
  reuse.
- `accumulator` — a two-argument callable `(container, element)` that folds
  one element into the container by mutating it. Its return value SHALL be
  ignored, matching Java's `BiConsumer<A,T>` and the already-shipped
  `Stream.collect(supplier, accumulator, combiner)` form.
- `combiner` — an optional two-argument callable merging two containers.
- `finisher` — an optional one-argument callable converting the finished
  container into the collected result. When omitted, the container itself
  SHALL be the result.

Each of the four parts MAY be a plain callable or an async one, and SHALL be
awaited when it is async, using the same sync-or-async dispatch every other
user-supplied callable in the library gets.

A `Collector` SHALL additionally carry `characteristics`, a set of
`Characteristics` members declaring traits of the collector. It is data rather
than a callable, so it is neither invoked nor awaited and the sync-or-async
rule above does not apply to it. It SHALL be the last part accepted at
construction, after `finisher`, and SHALL default to the empty set, so that
every `Collector` constructed without it — in this library or in user code —
behaves exactly as it did before this part existed.

#### Scenario: A user-defined Collector collects a stream
- **WHEN** `Stream.of([1, 2, 3]).collect(Collector(list, lambda c, e: c.append(e)))` is awaited
- **THEN** the result is `[1, 2, 3]`

#### Scenario: The finisher converts the container
- **WHEN** a `Collector` with `finisher=len` over a `list` container collects a 3-element stream
- **THEN** the result is `3`, not the list

#### Scenario: Omitting the finisher returns the container
- **WHEN** a `Collector` is constructed with no `finisher`
- **THEN** collecting a stream returns the accumulation container the supplier produced

#### Scenario: Async parts are awaited
- **WHEN** a `Collector` is constructed with an `async def` supplier, accumulator and finisher
- **THEN** the stream is collected correctly, each part awaited

#### Scenario: The accumulator's return value is ignored
- **WHEN** a `Collector`'s accumulator mutates its container and also returns an unrelated value
- **THEN** the collected result reflects only the mutation, and the returned value is discarded

#### Scenario: One Collector instance is reusable across streams
- **WHEN** the same `Collector` value is passed to `collect()` on two different streams, sequentially or concurrently
- **THEN** each collection produces its own result, with no state carried between them

#### Scenario: Omitting characteristics declares none
- **WHEN** a `Collector` is constructed without naming `characteristics`
- **THEN** its characteristics are empty, and it collects exactly as it does today

#### Scenario: Characteristics are readable from the constructed collector
- **WHEN** a `Collector` is constructed declaring `UNORDERED`
- **THEN** reading its characteristics reports `UNORDERED` present

### Requirement: `Characteristics` is the public vocabulary for a collector's traits

The library SHALL expose a public `Characteristics` enumeration, mirroring
Java's `Collector.Characteristics`, whose members describe traits of a
collector that a caller or the execution machinery may act on.

It SHALL define exactly one member, `UNORDERED`, meaning the collector does not
observe the encounter order of the elements it accumulates: for any two
orderings of the same elements, the collected result SHALL be equal.

`IDENTITY_FINISH` and `CONCURRENT` SHALL NOT be defined. The first is already
observable as the absence of a finisher, and defining it would allow two
statements of one fact to disagree. The second describes accumulating into one
shared container from independently reduced partitions, which the library has
no execution mode to produce — the `combiner` is accepted for signature parity
and never invoked. The enumeration SHALL be shaped so that either can be added
later without changing the meaning of `UNORDERED`.

`UNORDERED` SHALL be read by `collect()` to decide whether the pipeline must
deliver elements to the collector in encounter order. On an ordered racing
pipeline, a collector declaring `UNORDERED` SHALL be fed as the race resolves
elements, with no reorder barrier and no head-of-line delay; a collector not
declaring it SHALL be fed in encounter order (see the `racing-encounter-order`
capability).

Declaring `UNORDERED` SHALL NOT change the *value* a correct collector
produces. A collector declaring it asserts that its result is equal for any
ordering of the same elements; where that assertion holds, the declaration is
observable only as reduced latency and memory, never as a different result.
Where a caller declares it on a collector for which it does not hold, the
resulting order is unspecified and the caller has broken the contract.

Under the sequential executor the declaration SHALL have no effect at all.

#### Scenario: UNORDERED is a member of the public enumeration
- **WHEN** `Characteristics.UNORDERED` is referenced from the library's public
  surface
- **THEN** it resolves to a member of the `Characteristics` enumeration

#### Scenario: The other two Java characteristics are absent
- **WHEN** `IDENTITY_FINISH` or `CONCURRENT` is looked up on `Characteristics`
- **THEN** neither is defined

#### Scenario: Declaring UNORDERED does not change what is collected
- **WHEN** a sequential stream is collected with a collector declaring
  `UNORDERED`, and again with an otherwise identical collector declaring nothing
- **THEN** both collections produce equal results

#### Scenario: UNORDERED removes the delivery barrier under racing
- **WHEN** an ordered racing pipeline is collected with a collector declaring
  `UNORDERED`, and again with an otherwise identical collector declaring nothing
- **THEN** the declaring collection engages no reorder barrier and holds no
  element back, while the other delivers in encounter order

#### Scenario: to_set() takes the order-blind path
- **WHEN** an ordered racing pipeline is collected with `to_set()`
- **THEN** the collected set is correct and no reorder barrier was engaged

### Requirement: `combiner` is accepted but never invoked

A `Collector`'s `combiner` SHALL be accepted and retained for signature parity
with Java, and SHALL NOT be invoked, because a collection always folds over
one composed stream — sequential or parallel — with no independently
accumulated partitions to merge. This matches the posture
`Stream.collect(supplier, accumulator, combiner)` and `reduce`'s combiner
already have.

#### Scenario: The combiner is not called on a sequential stream
- **WHEN** a `Collector` whose combiner raises on call collects a sequential stream
- **THEN** the collection succeeds and the combiner is never called

#### Scenario: The combiner is not called on a parallel stream
- **WHEN** the same `Collector` collects a `.parallel()` stream
- **THEN** the collection succeeds, accumulating serially into one container, and the combiner is never called

### Requirement: `collect()` accepts a `Collector`, not an arbitrary callable

The single-argument `Stream.collect(collector)` SHALL accept a `Collector`
and drive the composed chain into it, returning an awaitable of the collected
result. Passing a callable that is not a `Collector` SHALL raise
`StreamBuildException`, with a message naming `Collector`, rather than being
called as a stream-consuming function.

Every collector the library ships SHALL be a factory returning a `Collector`,
with no exception, and SHALL be importable from `snakestream.collectors` —
the factory module, named for Java's `Collectors`, and separate from
`snakestream.collector`, which holds the `Collector` type itself. `to_list`
SHALL be called to obtain a collector — `collect(to_list())`, not
`collect(to_list)` — matching `to_set()`, `counting()`, `joining()` and every
other collector the library ships, and matching Java's `Collectors.toList()`.
Passing the bare `to_list` function object to `collect()` SHALL raise
`StreamBuildException` by the rule above, since a function is not a
`Collector`.

Each call to a collector factory SHALL return a collector that behaves
independently of any other: reusing one returned collector across two
collections SHALL still produce two independent results, since a `Collector`
holds no per-collection state.

#### Scenario: A library collector is accepted
- **WHEN** `Stream.of([1, 2, 3]).collect(counting())` is awaited
- **THEN** the result is `3`

#### Scenario: The factories are importable from `snakestream.collectors`
- **WHEN** `to_list`, `grouping_by`, `summing_int`, `min_by` and every other shipped collector factory is imported from `snakestream.collectors`
- **THEN** each import resolves, and each name is a factory returning a `Collector`

#### Scenario: The factories are no longer importable from `snakestream.collector`
- **WHEN** `from snakestream.collector import to_list` is executed
- **THEN** `ImportError` is raised — the factory module is `snakestream.collectors`

#### Scenario: `to_list()` is a factory like every other collector
- **WHEN** `Stream.of([1, 2, 3]).collect(to_list())` is awaited
- **THEN** the result is `[1, 2, 3]`

#### Scenario: `to_list` is usable without being called
- **WHEN** `Stream.of([1, 2, 3]).collect(to_list)` is awaited, passing the bare factory rather than calling it
- **THEN** it is not: `StreamBuildException` is raised, and the stream is not consumed

#### Scenario: One returned `to_list()` collector is reusable
- **WHEN** the same value returned by a single `to_list()` call is passed to two separate `collect()` calls on two streams
- **THEN** each call returns its own independent list, unaffected by the other

#### Scenario: A plain callable is rejected
- **WHEN** `collect()` is passed a stream-consuming `async def` that is not a `Collector` and is not `to_generator`
- **THEN** `StreamBuildException` is raised, and the stream is not consumed

#### Scenario: The 3-arg form is unaffected
- **WHEN** `Stream.of([1, 2, 3]).collect(list, list.append, list.extend)` is awaited
- **THEN** the result is `[1, 2, 3]`, exactly as before

### Requirement: `to_generator` is the one non-`Collector` collector

`to_generator` SHALL keep its existing shape — a callable taking the composed
`AsyncGenerator` and yielding its elements — and `collect(to_generator)` SHALL
keep returning an `AsyncGenerator` directly rather than an awaitable. It is
the documented exception to the rule above: it is lazy and streaming, and a
supplier/accumulator/finisher quadruple can only produce a value after the
source is exhausted.

Because it is a `StreamingCollector` value rather than a factory,
`to_generator` SHALL remain importable from `snakestream.collector`, alongside
the `Collector` type, and SHALL NOT move to `snakestream.collectors`.

#### Scenario: `collect(to_generator)` yields lazily
- **WHEN** `Stream.of([1, 3, 4, 5, 6]).filter(p).map(f).collect(to_generator)` is called
- **THEN** an `AsyncGenerator` is returned, not awaited, and iterating it yields the mapped elements in order

#### Scenario: `to_generator` does not need awaiting
- **WHEN** `collect(to_generator)` is called
- **THEN** the returned value is directly usable in `async for` with no `await` on `collect()` itself

#### Scenario: `to_generator` keeps its import path
- **WHEN** `from snakestream.collector import to_generator` is executed
- **THEN** it resolves, unchanged by the factory module split
