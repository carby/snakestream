## MODIFIED Requirements

### Requirement: limit() short-circuits without over-pulling upstream
`Stream.limit(n)` SHALL cause at most `n` elements to be pulled from the upstream source. An `(n+1)`th element SHALL NOT be pulled in order to discover that the limit has been reached.

This SHALL be delivered through the sink protocol's cancellation mechanism rather than by the operation closing its own upstream: `limit(n)`'s sink SHALL report `cancellation_requested()` as `True` once it has accepted `n` elements, and the loop driving the composed chain SHALL check that report after each `accept()` and stop pulling before issuing another pull. Closing the source SHALL be the responsibility of the driving loop, not of `limit()` itself.

The same no-over-pull guarantee SHALL hold when the cancellation originates at a **terminal** sink rather than at a mid-chain `limit()`: a driving loop that pushes into a terminal SHALL check the head sink's `cancellation_requested()` after each `accept()` and stop pulling before issuing another pull, and SHALL close the source on that early exit.

#### Scenario: limit() does not pull past the nth element
- **WHEN** a `Stream` chain containing `.peek(fn).limit(n)` is composed and consumed against a source with more than `n` elements
- **THEN** `fn` is called exactly `n` times, not `n + 1` times

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

### Requirement: flat_map() closes its per-element inner generator on early termination

`Stream.flat_map()`'s sink SHALL explicitly close the inner stream's composed generator for the outer element currently being processed, whether that inner generator is exhausted normally, raises, or is abandoned mid-iteration because downstream requested cancellation or the pipeline was torn down early (e.g. a downstream `.limit()`, or a short-circuiting terminal such as `any_match()` or `find_first()`). The inner stream SHALL be iterated through its own composition directly rather than through a `collect(to_generator)` wrapper, so there is a single generator layer to close.

`flat_map()`'s per-element inner loop SHALL stop as soon as downstream reports cancellation, regardless of whether that cancellation originated at a mid-chain `limit()` or at a terminal sink.

#### Scenario: Inner generator is closed when the outer chain short-circuits

- **WHEN** a chain `.flat_map(mapper).limit(n)` is composed and consumed, where `mapper(i)` for some outer element produces a tracked inner generator with `finally:` cleanup, and consumption stops (via `limit(n)`) while that inner generator is mid-iteration
- **THEN** the abandoned inner generator's `finally:` cleanup runs (i.e. `aclose()` was called on it)

#### Scenario: Inner generator is still closed on normal exhaustion

- **WHEN** a chain `.flat_map(mapper)` is composed and consumed to completion
- **THEN** every inner generator produced by `mapper(i)` for each outer element has been closed (either by natural exhaustion or explicit `aclose()`), with no change to the elements yielded compared to before this change

#### Scenario: Inner iteration stops when a terminal short-circuits

- **WHEN** a chain `.flat_map(mapper).find_first()` is driven, and the first outer element's inner stream has several elements
- **THEN** exactly one element is taken from that inner stream, its generator is closed, and no further outer element is pulled
