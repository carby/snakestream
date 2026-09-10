## MODIFIED Requirements

### Requirement: `collect()` accepts a `Collector`, not an arbitrary callable

The single-argument `Stream.collect(collector)` SHALL accept a `Collector`
and nothing else, and SHALL drive the composed chain into it, returning an
awaitable of the collected result. There SHALL be no second accepted shape:
every value `collect()` accepts in its single-argument form is a `Collector`,
and every one returns an awaitable. Passing anything that is not a `Collector`
SHALL raise `StreamBuildException`, with a message naming `Collector`, rather
than being called as a stream-consuming function.

A caller wanting a lazy, streaming handle on the pipeline SHALL use
`iterator()`, or iterate the stream directly. `collect()` SHALL NOT offer a
second route to one.

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
- **WHEN** `Stream([1, 2, 3]).collect(counting())` is awaited
- **THEN** the result is `3`

#### Scenario: The factories are importable from `snakestream.collectors`
- **WHEN** `to_list`, `grouping_by`, `summing_int`, `min_by` and every other shipped collector factory is imported from `snakestream.collectors`
- **THEN** each import resolves, and each name is a factory returning a `Collector`

#### Scenario: The factories are no longer importable from `snakestream.collector`
- **WHEN** `from snakestream.collector import to_list` is executed
- **THEN** `ImportError` is raised — the factory module is `snakestream.collectors`

#### Scenario: `to_list()` is a factory like every other collector
- **WHEN** `Stream([1, 2, 3]).collect(to_list())` is awaited
- **THEN** the result is `[1, 2, 3]`

#### Scenario: `to_list` is usable without being called
- **WHEN** `Stream([1, 2, 3]).collect(to_list)` is awaited, passing the bare factory rather than calling it
- **THEN** it is not: `StreamBuildException` is raised, and the stream is not consumed

#### Scenario: One returned `to_list()` collector is reusable
- **WHEN** the same value returned by a single `to_list()` call is passed to two separate `collect()` calls on two streams
- **THEN** each call returns its own independent list, unaffected by the other

#### Scenario: A plain callable is rejected
- **WHEN** `collect()` is passed a stream-consuming `async def` that is not a `Collector`
- **THEN** `StreamBuildException` is raised, and the stream is not consumed

#### Scenario: The 3-arg form is unaffected
- **WHEN** `Stream([1, 2, 3]).collect(list, list.append, list.extend)` is awaited
- **THEN** the result is `[1, 2, 3]`, exactly as before

#### Scenario: A lazy handle comes from `iterator()`, not from `collect()`
- **WHEN** a caller wants an `AsyncGenerator` over the composed pipeline rather than a collected value
- **THEN** `iterator()` returns one, and no argument to `collect()` does — every single-argument `collect()` returns an awaitable

#### Scenario: Every single-argument `collect()` is awaitable
- **WHEN** any value `collect()` accepts in its single-argument form is passed to it
- **THEN** the returned value is an awaitable of the collected result, with no case in which it is an `AsyncGenerator` to iterate instead

## REMOVED Requirements

### Requirement: `to_generator` is the one non-`Collector` collector

**Reason**: `collect(to_generator)` was a second spelling of `iterator()` — it
was implemented as `collector(self.iterator())`, and the wrapped callable
re-yielded that generator's elements under a close guard the element-producing
operation already applies. The duplicate spelling cost an extra generator layer
per element (+31% on a measured 200k-element `map` pipeline), had no Java
counterpart, and forced the one exception to "a collector is a `Collector` and
`collect()` returns an awaitable" through `collect()`'s dispatch and through
five other capabilities. Removing it removes the exception rather than
restating it.

**Migration**: Replace `.collect(to_generator)` with `.iterator()`, and drop
the `from snakestream.collector import to_generator` import. For the common
case of iterating the pipeline directly, `async for x in stream:` needs no
import at all. `StreamingCollector` is removed with it; a caller who wrapped
their own callable in it uses the generator returned by `iterator()` directly.
