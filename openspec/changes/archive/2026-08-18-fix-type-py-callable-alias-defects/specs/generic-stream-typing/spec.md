## ADDED Requirements

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
