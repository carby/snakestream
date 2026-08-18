## Context

`sorted()` (`stream.py:191`) has real, tested behavior and is referenced
three times in README's migration log, but the parity table itself never
got a row for it. This is a single-file documentation fix with no design
decisions to make.

## Goals / Non-Goals

**Goals:**
- Add an accurate `sorted()` row to README's Stream API table.

**Non-Goals:**
- No source, test, or behavior changes.
- No changes to any other table row.

## Decisions

- **Row placement**: alphabetical, between `skip()` and `to_array()`,
  matching the table's existing alphabetical ordering.
- **Signature shown**: `sorted(comparator: Comparator | None = None, reverse: bool = False)`,
  matching `stream.py:191` exactly.
- **Summary wording**: mirror Java's `Stream.sorted()`/`sorted(Comparator)`
  Javadoc phrasing, consistent with how other rows in the table (e.g.
  `min()`, `max()`) already phrase their Comparator-based summaries.

## Risks / Trade-offs

None — doc-only change to a single file, no code path affected.
