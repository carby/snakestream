# Collapse sort.py's decorate-sort-undecorate lanes

## Why

Everything below `sort()` is one algorithm — extract a column per segment, sort
on the columns, undecorate — but it is written once per lane rather than once.
`_sort_by_key()` has four `sorted(zip(rows, arr, strict=True), key=lambda pair:
pair[0], ...)` call sites (`sort.py:271,281,283,286`) and two identical
`[element for _, element in paired]` returns (`sort.py:272,288`). One level
down, `_column()` writes the same key/`None` re-interleave three times
(`sort.py:126-127,138-139,141-142`).

The three lanes in `_sort_by_key()` are not three algorithms. They are one
`sorted()` call over two derived values — the rows to sort on and whether to
reverse — and writing them as three branches means the shared `sorted()` and the
shared undecorate have to be repeated inside each. `_column()`'s three branches
are worse: they exist only to carry trial-call bookkeeping (`trial_i`, and two
comprehensions filtering on `i != trial_i`) that disappears entirely if the
non-`None` elements are extracted before the trial rather than indexed around.

The `_column()` half is already filed as roadmap **Next** item 3, and is the one
of that trio the roadmap marks free: `_column()` runs once per segment per sort,
never per element, so the gate that killed `add-callsite-dispatch` and
`collapse-terminal-collector-duplication` does not apply.

## What Changes

- **`_column()`: three re-interleaves become one.** Extract the non-`None`
  elements into a list first, so the sync trial is `results[0]` rather than an
  index to filter around. `trial_i`, the `next((i for i, element in
  enumerate(arr) ...), None)` scan and both `i != trial_i` comprehensions go
  away, and one private `_interleave(arr, values)` helper serves all three
  returns. The call set on every path is unchanged.
- **`_sort_by_key()`: four `sorted()` sites become one.** Each lane derives
  `rows` and `reverse`; the single `sorted()` and the single undecorate follow.
  The single-segment lane still builds no tuple (`rows` is the column itself),
  and the mixed lane still wraps only the descending columns in `_Descending`.
- **`key=lambda pair: pair[0]` becomes `key=operator.itemgetter(0)`**, moving
  the per-element key call from Python into C. Measured -10% on a single-segment
  sort of 20,000 elements and -6% on a two-segment one; see design.md, which
  also prices the two alternatives so they are not re-tried.
- **Not taken: folding the single-segment case into the general
  `asyncio.gather(...)` fan-out.** `gather` over one coroutine costs 9.1 us
  against 192 ns for a direct `await` — once per sort, so invisible on a large
  one and 4x the entire cost of sorting five elements. The fan-out branch stays,
  and is now separated from the lane choice rather than entangled with it.
  design.md carries the figures.
- **Not taken: `comparator.py`'s segment-sign 2x2**, roadmap **Next** item 1.
  Same neighbourhood, and the roadmap suggests this change as its warm-up, but it
  sits on a per-element path under a +10% ns/element gate. Bundling it would put
  a measured trade-off inside a change that otherwise has none.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. This is a pure refactor: same sorted order, same stability, same null
placement, same comparator invocation counts, same public surface.
`.openspec.yaml` sets `skip_specs: true` accordingly — the same posture
`extract-racing-task-lifecycle` and `sort-with-cmp-to-key` took for changes that
were measurable but not observable.

`comparator-contract`'s stability requirement is the regression gate rather than
something being restated: the all-descending lane keeps `reverse=True` (CPython's
strong stability, not a post-hoc reversal) and the mixed lane keeps ascending
`_Descending` tuples, so the rule that equal-comparing elements keep encounter
order is met by the same two mechanisms as before.

## Impact

- `src/snakestream/sort.py` only. One new private helper (`_interleave`), one new
  stdlib import (`operator.itemgetter`), four `sorted()` sites collapsed to one,
  three re-interleaves collapsed to one.
- **No test changes, including imports.** Nothing outside `ops.py` imports
  `snakestream.sort`, and `ops.py` imports only `sort`. No test reaches for
  `_column`, `_sort_by_key`, `_segment_column`, `_Descending`, `_tolerant_column`
  or `merge_sort`; the only occurrence of `merge_sort` under `tests/` is inside a
  comment at `tests/test_sorted.py:189`. All coverage is through
  `Stream.sorted()`.
- No README migration-log entry. Nothing a caller can observe changes, and that
  absence is a claim rather than an oversight.
- `roadmap.md` **Next** item 3 is closed by this change and must be removed from
  **Next** when it lands, with the decline of item 1 and of the gather fold
  recorded so neither is re-derived.
- `CLAUDE.md` does not describe `sort.py`'s internals, so it needs no edit.
