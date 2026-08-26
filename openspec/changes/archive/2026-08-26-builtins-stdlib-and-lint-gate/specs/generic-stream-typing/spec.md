## MODIFIED Requirements

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
