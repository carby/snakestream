## MODIFIED Requirements

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
