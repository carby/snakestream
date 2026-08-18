## Why

`Stream.sorted()` has been implemented since before the roadmap existed
(`stream.py:191`) but was never given a row in README's Stream API parity
table. The migration log references `sorted()` three times, which is what
makes the omission easy to miss — the table currently reads as if
`sorted()` doesn't exist.

## What Changes

- Add a `sorted(comparator: Comparator | None = None, reverse: bool = False)`
  row to README's Stream API table (the `x`-prefixed "done" table spanning
  lines 102-138), alphabetically positioned between `skip()` and `to_array()`.

## Capabilities

### New Capabilities

- `readme-parity-table`: README's Stream API table SHALL list a row for
  every implemented `Stream` method, so the table can be trusted as an
  accurate parity/API reference. Introduced here (rather than left
  undocumented) because this exact gap — an implemented method missing a
  row — is the bug this change fixes for `sorted()`.

### Modified Capabilities

None — `sorted()`'s existing runtime behavior is unchanged; only its
README documentation is being added.

## Impact

- `README.md` only. No source, test, or public API changes.
