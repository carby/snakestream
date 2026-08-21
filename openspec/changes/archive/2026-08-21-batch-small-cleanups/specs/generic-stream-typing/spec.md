## MODIFIED Requirements

### Requirement: Terminal operations are typed against the stream's element type
`collect()`, `reduce()`, `for_each()`, `find_any()`, `min()`, `max()`, `all_match()`, `any_match()`, `none_match()`, and `count()` SHALL be typed using the stream's bound `T`, so that user-supplied collectors/accumulators/consumers/predicates are checked against the actual element type rather than an unbound `TypeVar`.

#### Scenario: collect() return type follows the collector
- **WHEN** `Stream[int].collect(to_list())` is called
- **THEN** the result is typed as `list[int]`

#### Scenario: for_each() consumer is checked against the element type
- **WHEN** `Stream[int].for_each(consumer)` is called with a `consumer: Callable[[str], None]`
- **THEN** `ty` reports a type error, since the stream's `int` elements don't match the consumer's declared `str` parameter
