## MODIFIED Requirements

### Requirement: The ordering flag survives sequential()/parallel() mode switches
`BaseStream.sequential()` and `BaseStream.parallel()` SHALL propagate the
calling instance's current ordering flag onto the new instance they return,
rather than resetting it to the default. The ordering flag SHALL remain a
property of the stream, separate from the executor it carries: the executor
determines how a pipeline runs, the flag determines whether the caller requires
encounter order.

#### Scenario: unordered() survives a parallel() switch
- **WHEN** `.unordered()` is called on a sequential stream, followed by
  `.parallel()`
- **THEN** the resulting stream's `.is_ordered()` returns `False`

#### Scenario: unordered() survives a sequential() switch
- **WHEN** `.unordered()` is called on a parallel stream, followed by
  `.sequential()`
- **THEN** the resulting stream's `.is_ordered()` returns `False`

#### Scenario: An ordered stream stays ordered across a mode switch
- **WHEN** `.parallel()` (or `.sequential()`) is called on a stream that
  never had `.unordered()` called on it
- **THEN** the resulting instance's `.is_ordered()` still returns `True`
