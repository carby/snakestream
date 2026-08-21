## Purpose

Static typing guarantee that the element type flowing through a `Stream`/`ParallelStream` pipeline is tracked by the type checker (`ty`) end to end, instead of being `Unknown`, so mismatches like calling a `str`-only method on `int` elements are caught statically.

## Requirements

### Requirement: Stream classes are parameterized by element type
`BaseStream`, `Stream`, and `ParallelStream` SHALL be generic over the stream's current element type `T`, so that the static type checker (`ty`) knows the element type flowing through a pipeline instead of treating it as `Unknown`.

#### Scenario: Element type is known after construction
- **WHEN** a `Stream[int]` is constructed (e.g. `Stream.of([1, 2, 3])`)
- **THEN** `ty` infers its element type as `int`, not `Unknown`

#### Scenario: ParallelStream inherits the element type
- **WHEN** a `Stream[T]` is switched to parallel mode via `.parallel()`
- **THEN** the resulting `ParallelStream` is typed as `ParallelStream[T]` with the same element type

### Requirement: Type-changing intermediate operations update the element type
`map()` and `flat_map()` SHALL be typed so that the returned stream's element type reflects the mapper's declared return type, rather than preserving the input element type.

#### Scenario: map() changes the checked element type
- **WHEN** `Stream[int].map(mapper)` is called with a `mapper: Callable[[int], str]`
- **THEN** the returned stream is typed as `Stream[str]`

#### Scenario: Type checker catches a downstream misuse after map()
- **WHEN** code calls `.map()` with a mapper returning `int` and then calls a method that only exists on `str` on the result's elements
- **THEN** `ty` reports a type error

### Requirement: Type-preserving intermediate operations keep the element type
`filter()`, `distinct()`, `peek()`, `limit()`, and `sorted()` SHALL be typed to return the same element type `T` they were called on, since none of them can change what elements flow through the pipeline.

#### Scenario: filter() preserves element type
- **WHEN** `Stream[int].filter(predicate)` is called
- **THEN** the returned stream is typed as `Stream[int]`

### Requirement: Terminal operations are typed against the stream's element type
`collect()`, `reduce()`, `for_each()`, `find_any()`, `min()`, `max()`, `all_match()`, `any_match()`, `none_match()`, and `count()` SHALL be typed using the stream's bound `T`, so that user-supplied collectors/accumulators/consumers/predicates are checked against the actual element type rather than an unbound `TypeVar`.

#### Scenario: collect() return type follows the collector
- **WHEN** `Stream[int].collect(to_list())` is called
- **THEN** the result is typed as `list[int]`

#### Scenario: for_each() consumer is checked against the element type
- **WHEN** `Stream[int].for_each(consumer)` is called with a `consumer: Callable[[str], None]`
- **THEN** `ty` reports a type error, since the stream's `int` elements don't match the consumer's declared `str` parameter

### Requirement: StreamBuilder.build() returns a parameterized Stream
`StreamBuilder[T].build()` SHALL return `Stream[T]`, matching the element type already tracked by the builder, instead of an unparameterized `Stream`.

#### Scenario: Builder's element type flows into the built stream
- **WHEN** `StreamBuilder[int]().add(1).add(2).build()` is called
- **THEN** the result is typed as `Stream[int]`

### Requirement: Mapper and Consumer aliases declare sync-or-async support
The `Mapper` and `Consumer` type aliases in `type.py` SHALL declare both a synchronous and an `Awaitable`-wrapped return type, matching the existing `Predicate`/`Comparator` pattern and the actual sync-or-async dispatch (`_maybe_await`) performed by every operation that accepts a mapper or consumer (`map()`, `peek()`, `for_each()`, `for_each_ordered()`).

#### Scenario: Async mapper type-checks against Mapper
- **WHEN** a `Mapper[int, str]`-typed parameter is called with an `async def` function returning `Awaitable[str]`
- **THEN** `ty` accepts it without error

#### Scenario: Async consumer type-checks against Consumer
- **WHEN** a `Consumer[int]`-typed parameter is called with an `async def` function returning `Awaitable[None]`
- **THEN** `ty` accepts it without error

#### Scenario: Consumer's return value is not treated as a stream element
- **WHEN** a value is typed as `Consumer[T]`
- **THEN** its declared return type is `None | Awaitable[None]`, not `T`, since a consumer's return value is discarded

### Requirement: for_each and for_each_ordered are typed via the Consumer alias
`Stream.for_each()` and `Stream.for_each_ordered()` SHALL declare their `consumer` parameter using the `Consumer[T]` alias rather than an inline `Callable[[T], Any]` signature, matching `peek()`'s existing convention.

#### Scenario: for_each consumer parameter uses Consumer
- **WHEN** inspecting `Stream.for_each()`'s signature
- **THEN** the `consumer` parameter is typed as `Consumer[T]`

#### Scenario: for_each_ordered consumer parameter uses Consumer
- **WHEN** inspecting `Stream.for_each_ordered()`'s signature
- **THEN** the `consumer` parameter is typed as `Consumer[T]`
