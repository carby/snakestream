## Why

`sort.py`'s decorate-sort-undecorate has three lanes below `_sort_by_key()`, and
the mixed-direction one is the only place in the sort where a comparison runs in
Python rather than in C. A chain whose segments disagree on direction wraps its
descending columns in `_Descending`, whose `__lt__` is called once per pair the
earlier columns tie on. `collapse-sort-decorate-lanes` (2026-09-02) measured the
cost and accepted it — "~12ms all-ascending against ~40ms with the second segment
descending, roughly 3.3x" — while collapsing the four `sorted()` call sites
around it; the three alternatives it priced were all about the `key=` call, and
none of them was this one.

CPython's own sort guarantee removes the wrapper outright. Sorts are stable,
`reverse=True` included (it negates comparisons rather than reversing the list),
and the library documents the consequence: a series of stable sorts, least
significant key first, is exactly a lexicographic multi-key ordering with a
direction per key. That is what the three lanes are hand-building, once per
`sorted()` call, and it is available for free.

## What Changes

- Replace the tuple-building lanes in `_sort_by_key()` with **one successive-pass
  loop**: sort the paired rows once per column, least significant first, each
  pass carrying its own `reverse=`. Every comparison becomes a bare key
  comparison in C.
- **Delete `_Descending`** and the uniform/mixed lane split it exists for. The
  fan-out branch on `len(segments) == 1` stays (it decides only the fan-out, per
  `collapse-sort-decorate-lanes`), and so does the single-column lane, which
  already builds no tuple and compares in C.
- **BREAKING (behavioural, narrow):** a multi-segment chain now sorts *every*
  segment's column in full, where a lexicographic tuple comparison short-circuits
  on the first unequal component. A chain whose later segment yields mutually
  incomparable keys therefore raises `TypeError` whenever such a pair exists,
  rather than only where an earlier segment happened to tie on it. This makes the
  existing requirement hold unconditionally instead of holding wherever the data
  reached it; see the delta spec.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `comparator-chaining`: "Keys within a segment must be mutually comparable"
  strengthens. Today the `TypeError` surfaces only where a comparison on that
  segment is actually reached, which depends on whether earlier segments tie —
  so the same chain raises or does not raise depending on the data. It becomes
  unconditional: a segment holding mutually incomparable keys raises whatever the
  segments before it did.

## Impact

- `src/snakestream/sort.py` only: `_sort_by_key()`'s lane block, and the removal
  of `_Descending`.
- No public API surface changes. No signature, name or import a caller can see
  moves, so no README migration-log entry is owed.
- `sort.py` has no reachable test import — every existing test drives it through
  `Stream.sorted()` — so no test file, name or import is touched. The delta spec's
  new scenario is the one test this change adds.
- The measured figures in `_sort_by_key()`'s and `sort()`'s docstrings that name
  the mixed lane are superseded and must be rewritten against the shipped code.
