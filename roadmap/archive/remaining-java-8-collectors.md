+++
id = "remaining-java-8-collectors"
title = "Added the four remaining Java 8 `Collectors`"
filed = 2026-08-20
closed = 2026-08-20
outcome = "shipped"
+++

**Added the four remaining Java 8 `Collectors`** — `mapping(mapper,
downstream)`, `collecting_and_then(downstream, finisher)`,
`summarizing_int`/`summarizing_long`/`summarizing_double`, and
`to_collection(supplier)`. `mapping`/`collecting_and_then` are
downstream-adapting collectors built on the same downstream-`Collector`
composition `grouping_by`/`partitioning_by` already used; the `summarizing_*`
trio shares the `_summing` dispatch idiom and finishes to a new
`SummaryStatistics` `NamedTuple` rather than Java's mutable
`IntSummaryStatistics` — with `min`/`max` as `None` on an empty stream,
following `min_by`/`max_by`'s convention here instead of Java's sentinel
ints; and `to_collection` generalizes `to_list`/`to_set` to any
`add()`-supporting container. Additive, no public API change. This closes out
Java 8 `Collectors` parity, and unblocked the min/max/count/reduce collapse
that was a **Now** item at the time — since implemented in full, measured,
and rejected on cost (see the entry above). See
`openspec/changes/archive/2026-08-20-add-remaining-java8-collectors`.
