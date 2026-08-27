## MODIFIED Requirements

### Requirement: 3-arg mutable-reduction `collect(supplier, accumulator, combiner)`
`Stream.collect()` SHALL accept an overload taking exactly three positional arguments — `supplier`, `accumulator`, `combiner` — as an alternative to the existing single-arg `collect(collector)` form. `supplier` SHALL be called with no arguments exactly once to produce a fresh mutable result container. `accumulator` SHALL be called once per element pulled from the composed stream, as `accumulator(container, element)`, folding that element into the container. The call SHALL return the container once the composed stream is exhausted. Both `supplier` and `accumulator` MAY be sync or async callables, dispatched consistently with every other user-supplied callable in the codebase (`_maybe_await`).

#### Scenario: Sync supplier and accumulator build a list
- **WHEN** `Stream.of([1, 2, 3]).collect(list, list.append, list.extend)` is called
- **THEN** the result is `[1, 2, 3]`

#### Scenario: Async supplier and accumulator are awaited
- **WHEN** `collect()` is called with an `async def` supplier and an `async def` accumulator
- **THEN** both are awaited and the returned container reflects every element folded in via the accumulator

#### Scenario: Empty stream still returns a container
- **WHEN** `collect(supplier, accumulator, combiner)` is called on a stream with no elements
- **THEN** `supplier` is still called once and its untouched container is returned, with `accumulator` never called

#### Scenario: Existing single-arg `collect(collector)` is unaffected
- **WHEN** `collect(collector)` is called with exactly one positional argument
- **THEN** behavior is identical to before this change — `collector` is invoked directly against the stream's composed pipeline
