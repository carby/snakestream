## Why

`collector.py` has shipped every Java 8 `Collectors` static except four:
`collectingAndThen`, `mapping`, `summarizingInt`/`summarizingLong`/
`summarizingDouble`, and `toCollection(supplier)`. They were never picked up
as roadmap items, so they never went through the Now/Next/Later tracking the
rest of the `Collectors` effort went through, and README's parity table
still lists them as missing. The `Collector(supplier, accumulator, combiner,
finisher)` redesign these were sequenced behind has landed, so
`mapping`/`collectingAndThen` can now be built as downstream-collector
adapters and `summarizing*` can share the `_summing`/`_averaging` bodies
`summing_*`/`averaging_*` already established, rather than duplicating them.

## What Changes

- Add `mapping(mapper, downstream)`: a collector that maps each element via
  `mapper` before feeding it to `downstream`.
- Add `collecting_and_then(downstream, finisher)`: a collector that applies
  `downstream` and then runs its result through an additional `finisher`.
- Add `summarizing_int(mapper)`, `summarizing_long(mapper)`,
  `summarizing_double(mapper)`: collectors returning a summary-statistics
  result (count, sum, min, max, average) over the mapped values, mirroring
  Java's `IntSummaryStatistics`/`LongSummaryStatistics`/
  `DoubleSummaryStatistics`. The result type is a small immutable
  `NamedTuple` (`SummaryStatistics`) rather than a ported mutable-accumulator
  class, since nothing here needs post-hoc mutation.
- Add `to_collection(collection_supplier)`: a collector that accumulates
  elements into whatever container `collection_supplier()` returns (any
  object with an `add`-like method), generalizing `to_list`/`to_set`.
- Update README's Collectors table and migration/parity notes to list all
  four factories.

## Capabilities

### New Capabilities
- `collector-mapping`: `mapping(mapper, downstream)` downstream-adapting
  collector.
- `collector-collecting-and-then`: `collecting_and_then(downstream,
  finisher)` result-adapting collector.
- `collector-summarizing`: `summarizing_int`/`summarizing_long`/
  `summarizing_double(mapper)` collectors and the `SummaryStatistics` result
  type.
- `collector-to-collection`: `to_collection(collection_supplier)` collector.

### Modified Capabilities
None — these are additive factories with no change to existing collector
behavior or signatures.

## Impact

- `src/snakestream/collector.py`: four new public factories (plus a
  `SummaryStatistics` NamedTuple and any small shared helpers), following
  the existing `Collector(supplier, accumulator, finisher=...)` pattern and
  the `_check_downstream` guard `grouping_by`/`partitioning_by` already use
  for downstream collectors.
- `README.md`: Collectors table gains four rows; parity tracking no longer
  lists these as outstanding.
- No changes to `Stream`, `BaseStream`, sinks, or any existing collector's
  public signature.
