## ADDED Requirements

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

Declaring `UNORDERED` SHALL NOT by itself change any collected result. It is a
declaration about the collector, not an instruction to the pipeline; what reads
it is out of scope of this capability.

#### Scenario: UNORDERED is a member of the public enumeration
- **WHEN** `Characteristics.UNORDERED` is referenced from the library's public
  surface
- **THEN** it resolves to a member of the `Characteristics` enumeration

#### Scenario: The other two Java characteristics are absent
- **WHEN** `IDENTITY_FINISH` or `CONCURRENT` is looked up on `Characteristics`
- **THEN** neither is defined

#### Scenario: Declaring UNORDERED does not change what is collected
- **WHEN** a stream is collected with a collector declaring `UNORDERED`, and
  again with an otherwise identical collector declaring nothing
- **THEN** both collections produce equal results

## MODIFIED Requirements

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
