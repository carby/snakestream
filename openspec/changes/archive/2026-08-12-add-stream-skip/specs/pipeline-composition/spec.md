## ADDED Requirements

### Requirement: skip() drops the first n elements
`Stream.skip(n)` SHALL drop the first `n` elements pulled from its upstream
source and yield every element after that. If the upstream source has fewer
than `n` elements, `skip(n)` SHALL drain the source and yield nothing.

#### Scenario: skip() drops the first n elements of a longer source
- **WHEN** a `Stream` chain containing `.skip(n)` is composed and consumed
  against a source with more than `n` elements
- **THEN** the composed output omits the first `n` elements pulled from the
  source and contains every element after them, in order

#### Scenario: skip() on a source with fewer than n elements yields nothing
- **WHEN** a `Stream` chain containing `.skip(n)` is composed and consumed
  against a source with fewer than `n` elements
- **THEN** the composed output is empty

#### Scenario: skip(0) is a no-op
- **WHEN** a `Stream` chain containing `.skip(0)` is composed and consumed
- **THEN** the composed output is identical to the same chain without
  `.skip(0)`

### Requirement: Stateful sequential skip() closures reset per composition
For `Stream` (sequential, non-parallel) pipelines, the internal state used by
`skip()` (the count of elements dropped so far) SHALL be freshly initialized
at the start of each composition, not shared across separate compositions of
the same chain, following the same per-composition reset contract already
established for `distinct()`/`limit()`.

#### Scenario: skip() does not leak state across compositions
- **WHEN** a `Stream` chain containing `.skip(n)` is composed and consumed
  once, dropping the first `n` elements, and then the same chain is composed
  again against a new source
- **THEN** the second composition's `skip(n)` step drops up to `n` elements
  again, not zero

### Requirement: Parallel skip() remains globally correct across branches
For `ParallelStream` pipelines, the `skip()` step SHALL drop exactly the
first `n` elements pulled across all racing branches combined, not up to `n`
elements per branch. Because branches race independently, "first `n`" means
the first `n` elements pulled across all branches in whatever order the race
resolves them, not necessarily the first `n` elements in source order.

#### Scenario: Parallel skip() does not exceed n dropped in total
- **WHEN** a `ParallelStream` chain containing `.skip(n)` is composed against
  a source with more than `n` elements, racing across multiple branches
- **THEN** the composed output contains exactly `(source length - n)`
  elements in total across all branches, never fewer

#### Scenario: Parallel skip() state resets per composition
- **WHEN** a `ParallelStream` chain containing `.skip(n)` is composed and
  consumed once, and then the same chain is composed again against a new
  source
- **THEN** the second composition's shared drop-count starts fresh,
  independent of what any branch observed during the first composition
