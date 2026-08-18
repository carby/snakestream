## ADDED Requirements

### Requirement: flat_map() closes its per-element inner generator on early termination

`Stream.flat_map()`'s composed closure SHALL explicitly close the inner generator produced by `flat_mapper(i).collect(to_generator)` for the outer element currently being iterated, whether that inner generator is exhausted normally, raises, or is abandoned mid-iteration because the outer chain is torn down early (e.g. a downstream `.limit()` closing the pipeline via `GeneratorExit`). This closure SHALL cascade to the inner stream's own composed generator (i.e. `collector.py`'s `to_generator()` SHALL propagate `.aclose()` to the composition it wraps), so that a tracked source generator inside the inner stream actually observes cleanup, not just the `to_generator` wrapper.

#### Scenario: Inner generator is closed when the outer chain short-circuits

- **WHEN** a chain `.flat_map(mapper).limit(n)` is composed and consumed, where `mapper(i)` for some outer element produces a tracked inner generator with `finally:` cleanup, and consumption stops (via `limit(n)`) while that inner generator is mid-iteration
- **THEN** the abandoned inner generator's `finally:` cleanup runs (i.e. `aclose()` was called on it)

#### Scenario: Inner generator is still closed on normal exhaustion

- **WHEN** a chain `.flat_map(mapper)` is composed and consumed to completion
- **THEN** every inner generator produced by `mapper(i)` for each outer element has been closed (either by natural exhaustion or explicit `aclose()`), with no change to the elements yielded compared to before this fix
