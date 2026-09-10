## MODIFIED Requirements

### Requirement: flat_map() closes its per-element inner generator on early termination

`Stream.flat_map()`'s sink SHALL explicitly close the inner stream's composed generator for the outer element currently being processed, whether that inner generator is exhausted normally, raises, or is abandoned mid-iteration because downstream requested cancellation or the pipeline was torn down early (e.g. a downstream `.limit()`, or a short-circuiting terminal such as `any_match()` or `find_first()`). The inner stream SHALL be iterated through its own composition directly, with no wrapper generator between it and the sink, so there is a single generator layer to close.

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
