## Why

`collector.py` has no way to bucket a stream's elements by a derived key
into a `dict[K, list[T]]`, or split them into true/false buckets — Java's
`Collectors.groupingBy`/`partitioningBy`, two of the most-used `Collectors`
statics. This is the roadmap's declared last step of the `Collectors`-parity
effort tracked since `joining()`: `groupingBy`'s classifier reuses the same
key-mapper shape `to_map` already settled, and both accept an optional
downstream collector (e.g. `groupingBy(classifier, counting())`), which is
easiest to design now that several other `collect()`-compatible collectors
(`counting`, `summing_*`, `min_by`, `max_by`, `reducing`, `to_list`) already
exist to compose with.

## What Changes

- Add `grouping_by(classifier, downstream=to_list)` (`collector.py`) — a
  collector returning a `dict[K, R]` where elements are bucketed by
  `classifier(element)` (sync or async) into groups, and each group's
  elements are then reduced via `downstream` (any existing `collector.py`
  collector, default `to_list`), matching Java's
  `Collectors.groupingBy(classifier)` /
  `Collectors.groupingBy(classifier, downstream)`.
- Add `partitioning_by(predicate, downstream=to_list)` (`collector.py`) — a
  collector returning a `dict[bool, R]` with exactly the two keys `True`
  and `False` always present (even when one partition is empty), each
  mapped to that partition's elements reduced via `downstream`, matching
  Java's `Collectors.partitioningBy(predicate)` /
  `Collectors.partitioningBy(predicate, downstream)`.
- Update README's `Collectors` table with the two new rows.

## Capabilities

### New Capabilities
- `collector-grouping-by`: `grouping_by(classifier, [downstream])` collector
  factory bucketing stream elements by a derived key, with optional
  downstream-collector composition.
- `collector-partitioning-by`: `partitioning_by(predicate, [downstream])`
  collector factory splitting stream elements into `True`/`False` buckets,
  with optional downstream-collector composition.

### Modified Capabilities
(none — no existing requirement changes)

## Impact

- `src/snakestream/collector.py`: new `grouping_by`, `partitioning_by`
  functions, reusing `to_list` as the default downstream collector.
- `src/snakestream/type.py`: none expected — `Mapper` already covers
  `classifier`'s `T -> K` shape and `Predicate` already covers
  `predicate`'s shape; `downstream` is typed against the existing
  collector-closure shape (`Callable[[AsyncGenerator[T, None]], Coroutine[Any, Any, R]]`)
  each existing collector already returns.
- `README.md`: `Collectors` table gets two new rows.
- New tests: `tests/test_grouping_by.py`, `tests/test_partitioning_by.py`.
- No breaking changes; purely additive.
