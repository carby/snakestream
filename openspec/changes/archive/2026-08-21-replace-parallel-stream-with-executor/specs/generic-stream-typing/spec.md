## MODIFIED Requirements

### Requirement: Stream classes are parameterized by element type
`BaseStream` and `Stream` SHALL be generic over the stream's current element type `T`, so that the static type checker (`ty`) knows the element type flowing through a pipeline instead of treating it as `Unknown`. A mode switch SHALL preserve that element type, since it returns the same class carrying a different executor rather than a differently-typed class.

#### Scenario: Element type is known after construction
- **WHEN** a `Stream[int]` is constructed (e.g. `Stream.of([1, 2, 3])`)
- **THEN** `ty` infers its element type as `int`, not `Unknown`

#### Scenario: ParallelStream inherits the element type
- **WHEN** a `Stream[T]` is switched to parallel mode via `.parallel()`
- **THEN** the result is generic over the same element type — now `Stream[T]`, since execution mode is a value rather than a class, and `ParallelStream` was never exported so no published name changes
