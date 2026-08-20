## Purpose

Defines the `Collector` shape every `collector.py` factory returns — a
supplier/accumulator/combiner/finisher quadruple mirroring Java's
`Collector<T,A,R>` — and how `Stream.collect()` accepts and drives one.

## Requirements

### Requirement: `Collector(supplier, accumulator, combiner, finisher)` public shape

The library SHALL expose a public `Collector` type constructed from four
parts, mirroring Java's `Collector<T,A,R>`:

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

Every collector factory `collector.py` exposes SHALL return a `Collector`, and
`to_list` SHALL remain usable as a bare name — `collect(to_list)`, not
`collect(to_list())`.

#### Scenario: A library collector is accepted
- **WHEN** `Stream.of([1, 2, 3]).collect(counting())` is awaited
- **THEN** the result is `3`

#### Scenario: `to_list` is usable without being called
- **WHEN** `Stream.of([1, 2, 3]).collect(to_list)` is awaited
- **THEN** the result is `[1, 2, 3]`

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

#### Scenario: `collect(to_generator)` yields lazily
- **WHEN** `Stream.of([1, 3, 4, 5, 6]).filter(p).map(f).collect(to_generator)` is called
- **THEN** an `AsyncGenerator` is returned, not awaited, and iterating it yields the mapped elements in order

#### Scenario: `to_generator` does not need awaiting
- **WHEN** `collect(to_generator)` is called
- **THEN** the returned value is directly usable in `async for` with no `await` on `collect()` itself
