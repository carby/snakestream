## MODIFIED Requirements

### Requirement: `collect()` accepts a `Collector`, not an arbitrary callable

The single-argument `Stream.collect(collector)` SHALL accept a `Collector`
and drive the composed chain into it, returning an awaitable of the collected
result. Passing a callable that is not a `Collector` SHALL raise
`StreamBuildException`, with a message naming `Collector`, rather than being
called as a stream-consuming function.

Every collector `collector.py` exposes SHALL be a factory returning a
`Collector`, with no exception: `to_list` SHALL be called to obtain a
collector — `collect(to_list())`, not `collect(to_list)` — matching
`to_set()`, `counting()`, `joining()` and every other collector the library
ships, and matching Java's `Collectors.toList()`. Passing the bare
`to_list` function object to `collect()` SHALL raise `StreamBuildException`
by the rule above, since a function is not a `Collector`.

Each call to a collector factory SHALL return a collector that behaves
independently of any other: reusing one returned collector across two
collections SHALL still produce two independent results, since a `Collector`
holds no per-collection state.

#### Scenario: A library collector is accepted
- **WHEN** `Stream.of([1, 2, 3]).collect(counting())` is awaited
- **THEN** the result is `3`

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
