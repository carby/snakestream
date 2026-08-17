## Why

`collector.py` has `to_list`/`to_generator` and, as of the previous change,
`joining()` — but no numeric reducing collectors. Java's `Collectors.counting()`,
`summingInt`/`summingLong`/`summingDouble()`, and
`averagingInt`/`averagingLong`/`averagingDouble()` are roadmap.md's **Now**
item #1: the simplest remaining `Collectors` gap — each is a small fold
(count / running sum / running mean) over the composed generator, using the
same collector shape `joining()` already established, with no new machinery.

## What Changes

- Add `counting()` to `collector.py` — a zero-arg factory returning a
  collector that counts pulled elements, returning `int`.
- Add `summing_int(mapper)`, `summing_long(mapper)`, `summing_double(mapper)`
  — factories returning a collector that maps each element then sums the
  results. Kept as three separate, Java-parity-named functions (matching
  this project's stated naming preference) even though Python's numeric
  tower makes `summing_int`/`summing_long` behaviorally identical;
  `summing_double` explicitly coerces to `float`.
- Add `averaging_int(mapper)`, `averaging_long(mapper)`, `averaging_double(mapper)`
  — factories returning a collector that maps each element and returns the
  arithmetic mean as `float` (`0.0` for an empty stream, matching Java).
- Update README's `Collectors` table with the seven new entries.
- Move roadmap.md **Now** item #1 to **Done** once implemented.
- Not breaking: purely additive, seven new top-level functions in
  `collector.py`.

## Capabilities

### New Capabilities
- `collector-counting-summing-averaging`: numeric reducing collectors
  (`counting()`, `summing_int`/`summing_long`/`summing_double`,
  `averaging_int`/`averaging_long`/`averaging_double`) for use with
  `Stream.collect()`.

### Modified Capabilities
(none)

## Impact

- `collector.py`: seven new functions (`counting`, `summing_int`,
  `summing_long`, `summing_double`, `averaging_int`, `averaging_long`,
  `averaging_double`).
- `README.md`: seven new rows in the `Collectors` table.
- `roadmap.md`: move item #1 to **Done** once implemented.
- New `tests/test_counting.py`, `tests/test_summing.py`,
  `tests/test_averaging.py` (or a combined file — decided in tasks).
