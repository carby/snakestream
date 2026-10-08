+++
id = "to-map-and-to-set"
title = "Added `to_map()` and `to_set()`"
filed = 2026-08-18
closed = 2026-08-18
outcome = "shipped"
+++

Added `toMap(keyMapper, valueMapper, [mergeFunction])` / `toSet()`,
implemented as `to_map`/`to_set` (`collector.py`) — structural collectors
materializing into a `dict`/`set` instead of `to_list`'s `list`, matching
`Collectors.toMap`/`Collectors.toSet`. `to_map` maps each element to a
key/value pair via `key_mapper`/`value_mapper` (sync or async, dispatched
through `_maybe_await`); a duplicate key raises `ValueError` unless a
`merge_function` is given, in which case the collision resolves via
`merge_function(existing, new)`, matching Java's
`toMap(keyMapper, valueMapper, mergeFunction)` overload. `to_set()` takes
no arguments and simply collects into a `set`, deduplicating via
element `__hash__`/`__eq__` same as Java's `HashSet`-backed collector.
Added `tests/test_to_map.py`, `tests/test_to_set.py`. Updated README's
`Collectors` table with two new rows. No breaking changes. See
`openspec/changes/archive/2026-08-18-add-collectors-tomap-toset`.
