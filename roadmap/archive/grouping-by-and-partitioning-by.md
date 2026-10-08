+++
id = "grouping-by-and-partitioning-by"
title = "Added `grouping_by()` and `partitioning_by()`"
filed = 2026-08-18
closed = 2026-08-18
outcome = "shipped"
+++

Added `groupingBy(classifier, [downstream])` / `partitioningBy(predicate,
[downstream])`, implemented as `grouping_by`/`partitioning_by`
(`collector.py`) — `collector.py`'s equivalent of `Collectors.groupingBy`/
`partitioningBy`, closing out the roadmap's `Collectors`-parity effort.
Both bucket elements first (`grouping_by` via a `classifier` mapper into a
`dict[R, list[T]]`; `partitioning_by` via a `predicate` into a fixed
`{True: [...], False: [...]}`, always populating both keys even when one
partition is empty, matching Java's `Collectors.partitioningBy` exactly)
then re-drives each bucket's elements through an optional `downstream`
collector (default `to_list`) via a small `_generator_of(items)` helper
that re-wraps the buffered list as a fresh `AsyncGenerator`, since
downstream collectors are written to consume a composition, not a plain
list — enabling `grouping_by(classifier, counting())`-style composition
immediately, without downstream collectors needing to know they're being
reused this way. `grouping_by`'s `classifier` and `partitioning_by`'s
`predicate` reuse the same sync/async dispatch (`_maybe_await`) as every
other collector. Added `tests/test_grouping_by.py`,
`tests/test_partitioning_by.py`. Updated README's `Collectors` table with
two new rows. No breaking changes. See
`openspec/changes/archive/2026-08-18-add-collectors-groupingby-partitioningby`.
