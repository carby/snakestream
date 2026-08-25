## Purpose

`dict`-building collector for use with `Stream.collect()`, mirroring Java's
`Collectors.toMap(...)` overloads.

## Requirements

### Requirement: `to_map(key_mapper, value_mapper)` collector factory (no merge function)
`collector.py` SHALL provide a `to_map(key_mapper, value_mapper)` form —
called with no `merge_function` — returning a collector that builds a
`dict` by applying `key_mapper` and `value_mapper` (sync or async) to each
pulled element, matching Java's `Collectors.toMap(Function keyMapper,
Function valueMapper)`.

#### Scenario: builds a dict from key/value mappers
- **WHEN** `Stream.of([1, 2, 3]).collect(to_map(lambda x: x, lambda x: x * x))` is called
- **THEN** the result is `{1: 1, 2: 4, 3: 9}`

#### Scenario: empty stream yields an empty dict
- **WHEN** `Stream.of([]).collect(to_map(lambda x: x, lambda x: x))` is called
- **THEN** the result is `{}`

#### Scenario: async key_mapper and value_mapper are both awaited
- **WHEN** `to_map(key_mapper, value_mapper)` is given an async `key_mapper` and/or an async `value_mapper`
- **THEN** the result is computed correctly, with each awaited via the same dispatch used elsewhere in the library

### Requirement: `to_map` raises `IllegalStateException` on duplicate key with no merge function
When no `merge_function` is given and `key_mapper` produces the same key
for two different elements, `to_map`'s collector SHALL raise
`IllegalStateException` (from `snakestream.exception`), matching Java's
`Collectors.toMap(keyMapper, valueMapper)` throwing `IllegalStateException`
on a duplicate key. The raised exception SHALL name the colliding key.

`IllegalStateException` is a direct subclass of `Exception` and SHALL NOT be
made a subclass of `ValueError`: a caller catching `ValueError` around a
`to_map` collection no longer catches this.

#### Scenario: duplicate key without a merge function raises IllegalStateException
- **WHEN** `Stream.of(["a", "aa", "b"]).collect(to_map(lambda x: len(x), lambda x: x))` is called
- **THEN** an `IllegalStateException` is raised, since `"a"` and `"b"` both map to key `1`

#### Scenario: duplicate key is no longer a ValueError
- **WHEN** `Stream.of(["a", "aa", "b"]).collect(to_map(lambda x: len(x), lambda x: x))` is called inside a `try` that catches only `ValueError`
- **THEN** the `IllegalStateException` propagates uncaught, since it does not derive from `ValueError`

### Requirement: `to_map(key_mapper, value_mapper, merge_function)` resolves duplicate keys
`collector.py` SHALL provide the 3-arg `to_map(key_mapper, value_mapper,
merge_function)` form, where a duplicate key's colliding value is resolved
by calling `merge_function(existing_value, new_value)` (sync or async)
instead of raising, matching Java's `Collectors.toMap(keyMapper,
valueMapper, mergeFunction)`.

#### Scenario: duplicate key is resolved via merge_function
- **WHEN** `Stream.of(["a", "aa", "b"]).collect(to_map(lambda x: len(x), lambda x: x, lambda a, b: a + b))` is called
- **THEN** the result is `{1: "ab", 2: "aa"}`

#### Scenario: async merge_function is awaited
- **WHEN** `to_map(key_mapper, value_mapper, merge_function)` is given an async `merge_function` and a duplicate key occurs
- **THEN** the result is computed correctly, with `merge_function` awaited via the same dispatch used elsewhere in the library

#### Scenario: no collision means merge_function is never called
- **WHEN** `Stream.of([1, 2, 3]).collect(to_map(lambda x: x, lambda x: x, merge_function))` is called with all-distinct keys
- **THEN** the result is `{1: 1, 2: 2, 3: 3}` and `merge_function` is never invoked
</content>
