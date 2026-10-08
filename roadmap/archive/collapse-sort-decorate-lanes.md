+++
id = "collapse-sort-decorate-lanes"
title = "`sort.py`'s decorate-sort-undecorate is written once (`collapse-sort-decorate-lanes`)"
filed = 2026-09-02
closed = 2026-09-02
outcome = "shipped"
shipped_as = "collapse-sort-decorate-lanes"
+++

**`collapse-sort-decorate-lanes`** (2026-09-02) — closes **Next**'s former
item 3. `sort.py`'s decorate-sort-undecorate was written once per lane
rather than once: `_column()` re-interleaved gathered keys against `None`
three times, carrying `trial_i` and two `i != trial_i` comprehensions purely
to skip recomputing a trial call's own result, and `_sort_by_key()` had four
`sorted(zip(rows, arr, strict=True), key=lambda pair: pair[0], ...)` call
sites and two identical undecorate returns. Both run once per segment or
once per `sorted()` call, never once per element, so — unlike every other
duplication in this neighbourhood — no `+10%` gate applied to either
collapse.

**`_column()`:** extracting the non-`None` elements into a `present` list
first turns the sync trial into `results[0]`, and `trial_i` plus both
`i != trial_i` filters have nothing left to guard; one `_interleave(arr,
values)` helper now serves all three return paths. The invocation-count
claim the rewrite rests on — every path calls the extractor exactly once
per non-`None` element, the sync-that-lied path's trial element included —
was checked directly with a counting extractor across all three paths
before being trusted.

**`_sort_by_key()`:** the `len(segments) == 1` fan-out branch now decides
only the fan-out (`columns = [await _segment_column(...)]` vs. the existing
`asyncio.gather`); a `len(columns) == 1` lane below it handles the
no-tuple-build question separately. All four lanes reduce to deriving
`(rows, reverse)` and falling through to one `sorted(zip(rows, arr,
strict=True), key=itemgetter(0), reverse=reverse)` and one undecorate. The
three measured claims in its docstring survive structurally, verified
against the shipped code rather than re-measured: the single-segment lane
binds `rows` to the column itself (no `tuple(...)`), the uniform lane
reaches `sorted(reverse=...)` directly (CPython's strong stability, not a
post-hoc reversal), and the mixed lane still wraps only descending columns
in `_Descending`.

**`operator.itemgetter(0)` replaces `lambda pair: pair[0]`** in the
now-single `sorted()` call — a C callable in place of a Python frame, on a
key invoked once per element by the sort. Python 3.14.5, 20,000 elements,
interleaved per round to remove cross-invocation drift, best of 7, three
independent runs:

| shape | delta (`itemgetter` vs. `lambda`) |
|---|---|
| 1 segment, scalar keys | −12.4% / −19.3% / −20.9% |
| 2 segments, tuple keys | −3.6% / −7.7% / −5.0% |

Consistently negative on both shapes across all three runs, at or past the
exploration's −10% / −6% figures. **Three alternatives priced and
declined, recorded so none is re-derived:** `(key, index)` decoration with
no `key=` at all — plain tuple comparison, zero Python-level key calls —
measured **worse**, 5.71 ms against 3.27 ms, because the tuple comparison
costs more than the key calls it saves, and it would additionally need a
negated index under `reverse=True` to keep ties in encounter order.
`sorted(range(len(arr)), key=keys.__getitem__)` over indices measured
2.97 ms, a tie with `itemgetter` within noise, and it forces the
multi-segment lanes to materialise their zipped rows as a list to stay
indexable — no clearer, no faster. Folding the single-segment fan-out into
the general `asyncio.gather(...)` would remove a branch but costs 9.1 us
against 192 ns for a direct `await`, once per sort — roughly 4x the entire
cost of sorting five elements, and small sorts are the common case for a
tie-break chain — so the fan-out branch stays, now deciding only the
fan-out rather than the fan-out and the lane and the undecorate together.

**`comparator.py`'s segment-sign 2x2 — the remaining item from the same
read, still in Next — was deliberately left out of this change**, not
overlooked: it sits on a per-element path (`min()`/`max()`,
`min_by()`/`max_by()`, one comparison per element) under the
`collapse-terminal-collector-duplication` `+10%` ns/element gate, and
bundling it would put a measured trade-off inside a change that otherwise
has none. It stays queued on its own gate.

988 tests green, unchanged from before — `git diff --stat tests/` empty, no
test file, name or import touched (`sort.py` has no reachable test import;
all coverage runs through `Stream.sorted()`). Coverage 98.62%; `sort.py`
shrank from 117 to 111 statements and 40 to 38 branches, 0 missed and 100%
both before and after — the five removed branches were fully covered, not
under-tested, so no arm went silently unreachable. No README migration-log
entry, and that absence is a claim: nothing a caller can observe changed.
`skip_specs: true`.
