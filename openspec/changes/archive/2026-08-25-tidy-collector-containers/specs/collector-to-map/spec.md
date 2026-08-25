## ADDED Requirements

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

## REMOVED Requirements

### Requirement: `to_map` raises on duplicate key with no merge function
**Reason**: The raised type moves from `ValueError` to `IllegalStateException`
for parity with Java's `Collectors.toMap`, which throws
`IllegalStateException`. Replaced by the ADDED requirement above; the
behaviour it governs (raise on a duplicate key when no `merge_function` was
given) is unchanged, only the exception type is.
**Migration**: Call sites catching `ValueError` around a two-argument
`to_map` collection must catch `snakestream.exception.IllegalStateException`
instead. This breaks loudly for `except ValueError`; a bare `except` or an
`except Exception` is unaffected. Call sites passing a `merge_function` never
reached this path and need no change.
