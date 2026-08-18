## Why

`collector.py` currently only materializes a composed stream into a `list`
(`to_list`) or a `str` (`joining`) — there's no `collect()`-compatible way to
get a `dict` or `set` out of a stream, even though both are common terminal
shapes and Java's `Collectors.toMap`/`Collectors.toSet` are among the most
used collectors in the API being mirrored. This is also the roadmap's
declared first step before `groupingBy`/`partitioningBy`: `groupingBy`'s
classifier is the same key-mapper shape `toMap` needs to settle, and
`toMap`'s duplicate-key-merge convention is exactly what a downstream
`groupingBy` will reuse.

## What Changes

- Add `to_map(key_mapper, value_mapper, merge_function=None)` (`collector.py`)
  — a collector returning a `dict` built by applying `key_mapper`/
  `value_mapper` (sync or async) to each element. With no `merge_function`,
  a duplicate key raises, matching Java's `Collectors.toMap(keyMapper,
  valueMapper)` throwing `IllegalStateException` on collision. With a
  `merge_function` given (matching Java's 3-arg overload), a colliding key's
  new value is folded with the existing one via `merge_function(existing,
  new)` (sync or async) instead of raising.
- Add `to_set()` (`collector.py`) — a collector returning a `set` of the
  stream's elements, matching Java's `Collectors.toSet()`. Unlike Java, no
  ordering/mutability guarantee is claimed since Python's `set` already has
  none.
- Update README's `Collectors` table with the two new rows.

## Capabilities

### New Capabilities
- `collector-to-map`: `to_map(key_mapper, value_mapper, [merge_function])`
  collector factory materializing a composed stream into a `dict`, including
  duplicate-key handling (raise by default, merge when `merge_function` is
  given).
- `collector-to-set`: `to_set()` collector factory materializing a composed
  stream into a `set`.

### Modified Capabilities
(none — no existing requirement changes)

## Impact

- `src/snakestream/collector.py`: new `to_map`, `to_set` functions.
- `src/snakestream/type.py`: none expected — `Mapper` already covers
  `key_mapper`/`value_mapper`'s shape and `BinaryOperator` already covers
  `merge_function`'s shape (both pre-existing aliases, reused as-is).
- `README.md`: `Collectors` table gets two new rows.
- New tests: `tests/test_to_map.py`, `tests/test_to_set.py`.
- No breaking changes; purely additive.
