## Context

See proposal.md — Why. What matters here is the shape of `_sort_by_key()` as it
stands after `collapse-sort-decorate-lanes` (2026-09-02): a fan-out branch on
`len(segments) == 1` that decides only whether the columns are gathered, then a
three-way lane block that derives `(rows, reverse)`, then one
`sorted(zip(rows, arr, strict=True), key=itemgetter(0), reverse=reverse)` and one
undecorate.

The three lanes exist to express one thing — a lexicographic ordering with a
direction per column — in three ways:

```
  len(columns) == 1        rows = the column itself,  reverse = its direction
  all/none descending      rows = zip(*columns),      reverse = all(directions)
  mixed                    rows = zip(*columns) with descending entries
                           wrapped in _Descending,    reverse = False
```

Only the third pays a Python-level comparison, and it pays it once per pair that
ties on every earlier column.

## Goals / Non-Goals

**Goals.** One code path for every multi-segment chain, whatever its directions.
Every comparison in C. `_Descending` gone. The observable incomparability rule
made independent of the data.

**Non-Goals.** The `len(segments) == 1` fan-out branch is not touched —
`collapse-sort-decorate-lanes` priced folding it into the general
`asyncio.gather(...)` at 9.1 us against 192 ns for a direct `await` and declined,
and nothing here revisits that. Null placement, `reversed()`, stability and the
async-extraction concurrency are all unchanged; this rewrites how already-extracted
columns are sorted and nothing upstream of that. `merge_sort()` and the sync
`cmp_to_key` path are out of scope entirely.

## Decisions

### 1. Successive stable passes, least significant column first

CPython guarantees `list.sort()` is stable and that `reverse=True` is stable in
the strong sense — it negates comparisons rather than reversing the result — and
the library documents the consequence directly: a series of stable sorts, least
significant key first, composes into a multi-key ordering. Running one pass per
column with that column's own `reverse=` is therefore *exactly* the lexicographic
order the tuple lanes build, ties included.

```
  paired = sorted(zip(*columns, arr), key=itemgetter(last), reverse=directions[last])
  for i in reversed(range(last)):
      paired.sort(key=itemgetter(i), reverse=directions[i])
```

The first pass is a `sorted()` rather than a `list()` plus a `.sort()` so that a
single-column chain reduces to precisely the call it makes today.

**Alternative considered — rank the descending columns.** Replace each descending
column's keys with the negated rank of the key among that column's distinct
values, then take the existing all-ascending tuple lane. It keeps one Timsort
pass, but it needs either hashable keys (which a comparator segment's
`cmp_to_key` objects are not) or a second index sort per column to compute ranks
without hashing — more machinery than the wrapper it replaces, for a shape the
successive passes already beat.

**Alternative considered — keep `_Descending`, make it cheaper.** There is no
cheaper version: any Python object participating in a tuple comparison costs a
Python frame per comparison, which is the entire charge.

### 2. All multi-segment chains take the new path, not only the mixed ones

Applying it to the mixed lane alone is the faster option on chains of five or
more uniform segments, and it was the first scope considered. It is rejected
because it makes an *observable* behaviour depend on which lane the data lands
in: under Decision 1 every column is sorted in full, so a segment holding
incomparable keys raises — and if only mixed chains took that path, then
`comparing(a).then_comparing(b)` and the same chain with `b` reversed would
differ in whether they raise `TypeError` on identical data. The roadmap's guiding
principle rules that out: a divergence in observable behaviour is a defect. One
path, one rule.

The cost is charged where nobody is: uniform chains of five or more segments (see
Risks).

### 3. The strengthened incomparability rule is spec'd, not merely accepted

Today's `TypeError` surfaces where a comparison is reached, and a lexicographic
tuple comparison short-circuits — so a chain whose second segment yields
incomparable keys sorts happily on data whose first segment never ties, and
raises on data where it does. That is a latent failure keyed on the input.
Sorting each column in full makes the raise a property of the keys alone, which
is what `comparator-chaining`'s requirement already says it is; the delta writes
down the unconditional form and adds the scenario that distinguishes them.

### 4. `map(itemgetter(-1))` for the undecorate

The rows are now variable-length (`k` columns plus the element), so the existing
`[element for _, element in paired]` unpacking cannot express the undecorate.
`list(map(itemgetter(-1), paired))` keeps it in C, and measured level with the
unpacking form; a `[row[-1] for row in paired]` comprehension measured ~4% worse
on the single-segment shape.

## Risks / Trade-offs

**Measured, Python 3.14.5, 20,000 rows, best of 11, outputs asserted
element-identical to the current lanes at every shape including tie order:**

| shape | current | successive | |
|---|---|---|---|
| mixed, 2 segments | 34.8 ms | 5.1 ms | **6.8x** |
| mixed, 4 segments | 39.1 ms | 7.9 ms | **4.9x** |
| mixed, 8 segments | 50.9 ms | 11.4 ms | **4.5x** |
| uniform, 2 segments | 7.0 ms | 5.0 ms | 1.39x |
| uniform, 3 segments | 7.5 ms | 6.2 ms | 1.22x |
| uniform, 4 segments | 7.4 ms | 7.0 ms | 1.06x |
| uniform, 5 segments | 7.8 ms | 8.4 ms | **0.93x** |
| uniform, 8 segments | 8.2 ms | 12.0 ms | **0.68x** |
| single segment, n=20 | 1.8 us | 2.4 us | **0.78x** |

Also measured with distinct keys throughout (20,000 distinct rather than 200, so
that earlier columns rarely tie and the tuple lanes short-circuit at their best):
mixed still 3.45x / 2.66x at k=2 / k=3, uniform 1.08x / 1.11x. The mixed win
does not depend on a tie-heavy input.

- **[Uniform chains of five or more segments regress, 0.93x to 0.68x]** → Accepted
  and recorded rather than mitigated. `k` passes of C comparison eventually lose
  to one short-circuiting tuple comparison, and the crossover sits between four
  and five segments. A five-segment `then_comparing()` chain is not a shape this
  library has seen; the two- and three-segment chains that are the realistic case
  are 1.39x and 1.22x *faster*. Anyone who finds the long-chain shape in the wild
  should reopen Decision 2, not this row.
- **[The single-segment lane pays ~0.6 us per call]** → Mitigated by keeping it.
  The fixed cost is the `zip(*columns, arr)` star-unpack plus the `map` over a
  one-column row, and on a 20-element sort it is 30% of a very small number.
  Decision 1's first-pass `sorted()` keeps `len(columns) == 1` on the call it
  makes today.
- **[A supplied comparator segment is invoked more often]** → Accepted. A
  comparator segment's column is `cmp_to_key`-wrapped, so fully sorting that
  column invokes the caller's comparator where a short-circuiting tuple
  comparison would not have. No requirement bounds that count — only key
  *extractions* are spec'd at exactly one per element, and those are unchanged,
  since the columns are still extracted once before any sorting begins.
- **[The docstring figures go stale]** → `_sort_by_key()`'s docstring names the
  three lanes and carries the 3.3x mixed-lane figure, and `sort()`'s references
  the fast path. Both are rewritten against the shipped code as a task, not left
  to describe a structure that no longer exists.

## Migration Plan

None. `sort.py` is entirely private, the change is one function body plus a
deleted class, and no caller-visible name moves. Rollback is a revert.
