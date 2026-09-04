## Purpose

Static typing guarantee that the element type flowing through a `Stream` pipeline, regardless of execution mode, is tracked by the type checker (`ty`) end to end, instead of being `Unknown`, so mismatches like calling a `str`-only method on `int` elements are caught statically.

## Requirements

### Requirement: Stream classes are parameterized by element type
`Stream` SHALL be generic over the stream's current element type `T`, so that the static type checker (`ty`) knows the element type flowing through a pipeline instead of treating it as `Unknown`. A mode switch SHALL preserve that element type, since it returns the same class carrying a different executor rather than a differently-typed class.

#### Scenario: Element type is known after construction
- **WHEN** a `Stream[int]` is constructed (e.g. `Stream.of([1, 2, 3])`)
- **THEN** `ty` infers its element type as `int`, not `Unknown`

#### Scenario: A RACING stream inherits the element type
- **WHEN** a `Stream[T]` is switched to the fork-join executor via `.parallel()`
- **THEN** the result is generic over the same element type — still `Stream[T]`, since execution mode is a value rather than a class, and the retired parallel-stream class was never exported so no published name changes

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

`Mapper[T, R]`'s declared return type SHALL be exactly `R | Awaitable[R]`: it SHALL NOT admit `None` as a separate arm of that union. A mapper that returns `None` is expressed by binding `R` to `None`, so the extra arm adds no expressiveness while widening every `.map()` result to an optional element type, contradicting the requirement that `Stream[int].map(mapper)` with a `mapper` returning `str` is typed `Stream[str]`.

Where a `None` arm is genuinely part of an alias's contract — as in `Consumer`, whose return value is discarded — `None` SHALL be declared at the end of the union rather than in the middle of it.

#### Scenario: Async mapper type-checks against Mapper
- **WHEN** a `Mapper[int, str]`-typed parameter is called with an `async def` function returning `Awaitable[str]`
- **THEN** `ty` accepts it without error

#### Scenario: Async consumer type-checks against Consumer
- **WHEN** a `Consumer[int]`-typed parameter is called with an `async def` function returning `Awaitable[None]`
- **THEN** `ty` accepts it without error

#### Scenario: Consumer's return value is not treated as a stream element
- **WHEN** a value is typed as `Consumer[T]`
- **THEN** its declared return type is `Awaitable[None] | None`, not `T`, since a consumer's return value is discarded

#### Scenario: map() does not widen the element type to optional
- **WHEN** `Stream[int].map(mapper)` is called with a `mapper: Callable[[int], str]`
- **THEN** the result is typed `Stream[str]`, not `Stream[str | None]`

#### Scenario: A mapper returning None is still expressible
- **WHEN** a mapper's declared return type is `None` (or `str | None`)
- **THEN** it type-checks against `Mapper[T, R]` with `R` bound to that type, and the resulting stream's element type is that same type

### Requirement: for_each and for_each_ordered are typed via the Consumer alias
`Stream.for_each()` and `Stream.for_each_ordered()` SHALL declare their `consumer` parameter using the `Consumer[T]` alias rather than an inline `Callable[[T], Any]` signature, matching `peek()`'s existing convention.

#### Scenario: for_each consumer parameter uses Consumer
- **WHEN** inspecting `Stream.for_each()`'s signature
- **THEN** the `consumer` parameter is typed as `Consumer[T]`

#### Scenario: for_each_ordered consumer parameter uses Consumer
- **WHEN** inspecting `Stream.for_each_ordered()`'s signature
- **THEN** the `consumer` parameter is typed as `Consumer[T]`
