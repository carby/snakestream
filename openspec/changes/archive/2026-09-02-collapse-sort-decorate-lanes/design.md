## Context

See proposal.md — Why. Two constraints shape the approach, and both come from
figures rather than taste.

`_column()` and `_sort_by_key()` sit **once per sort**, not once per element:
`_column()` runs once per segment, `_sort_by_key()` once per `sorted()` call.
That is what makes this change gate-free, and it is the only structural
difference between it and the three duplications the roadmap's **Done** log
records as measured and declined.

The one exception is the `key=` callable, which the C sort invokes once per
element inside an O(n log n) pass. That is a per-element path and is treated as
one below.

`_sort_by_key()`'s docstring already carries three measured claims that this
change must not break: the single-ascending-segment path costs "one column, no
tuple build, no outer gather"; `reverse=True` equals comparator negation exactly
because CPython's sort is stable in the strong sense; and the mixed lane's
`_Descending` wrapper is paid "only on the columns that asked for one".

## Goals / Non-Goals

**Goals:**

- One `sorted()` call site and one undecorate in `_sort_by_key()`, with each
  lane reduced to the two values it actually differs in.
- One re-interleave in `_column()`, with the trial-call index bookkeeping gone.
- The three measured claims above preserved, and verifiable from the shipped
  code without re-measuring.

**Non-Goals:**

- Changing the number of extractor or comparator invocations on any path. This
  change moves where results are collected, never how many calls produce them.
- Touching `sort()`, `merge_sort()`, `_merge()`, `_checked()`,
  `_checked_segment_comparator()`, `_segment_column()`, `_Descending`,
  `_presence_markers()` or `_tolerant_column()`.
- Any change under `tests/`, including imports.

## Decisions

### Decision 1: a lane derives `(rows, reverse)`; the sort and the undecorate are shared

The three lanes differ in exactly two values, and every other line in them is
identical. Deriving those two and falling through to one `sorted()` is what
removes three call sites:

```python
if len(columns) == 1:
    rows, reverse = columns[0], directions[0]
elif all(directions) or not any(directions):
    rows, reverse = zip(*columns, strict=True), all(directions)
else:
    rows = (
        tuple(_Descending(v) if d else v for v, d in zip(row, directions, strict=True)) for row in zip(*columns, strict=True)
    )
    reverse = False

paired = sorted(zip(rows, arr, strict=True), key=itemgetter(0), reverse=reverse)
return [element for _, element in paired]
```

Each of the three claims survives structurally rather than by re-measurement.
The single-segment lane binds `rows` to the column itself, so no tuple is built.
The uniform lane still reaches `sorted(reverse=...)` directly, so it is still
CPython's strongly-stable reverse rather than a post-hoc reversal. The mixed
lane still wraps per column under `if d`, so an ascending column in a mixed
chain still pays nothing.

**Alternative considered: keep the `len(segments) == 1` early return and collapse
only the three multi-segment lanes.** Rejected. It saves two of the four
`sorted()` sites instead of three and leaves the single-segment path with its own
undecorate, which is the line the collapse exists to remove. It also keeps the
fan-out decision and the lane decision entangled, which Decision 3 separates.

### Decision 2: `operator.itemgetter(0)` in place of `lambda pair: pair[0]`

The `key=` callable is invoked once per element by a C sort. `itemgetter` is a C
callable; the lambda is a Python frame. Python 3.14.5, 20,000 elements, best of 7:

| shape | `lambda pair: pair[0]` | `itemgetter(0)` |
|---|---|---|
| 1 segment, scalar keys | 3.35 ms | **3.03 ms** (-10%) |
| 2 segments, tuple keys | 5.88 ms | **5.52 ms** (-6%) |

Recorded here so neither is re-tried:

- **`(key, index)` decoration with no `key=` at all** — plain tuple comparison,
  zero Python-level key calls, ties broken by the index. **Worse: 5.71 ms against
  3.27 ms.** The tuple comparison costs more than the key calls it saves, and it
  would additionally need a negated index under `reverse=True` to keep ties in
  encounter order, which is complexity bought for a regression.
- **`sorted(range(len(arr)), key=keys.__getitem__)` over indices** — 2.97 ms,
  a tie with `itemgetter` within noise, and it forces the multi-segment lanes to
  materialise their zipped rows as a list to be indexable. No clearer, no faster.

This is the only per-element change in the proposal, and it moves the number the
right way, so no gate applies to it either.

### Decision 3: the single-segment fan-out branch stays, and moves

Folding `len(segments) == 1` into the general `asyncio.gather(...)` would remove
a branch. It costs a real number: `gather` over one coroutine measured **9.1 us**
against **192 ns** for a direct `await` (Python 3.14.5, 20,000 iterations).

Once per sort, so it is invisible at 20,000 elements and roughly 4x the entire
cost of sorting five — and small sorts are the common case for a tie-break chain.
`_sort_by_key()`'s docstring already claims "no outer gather" for this path, so
folding would be retracting a documented claim to buy one branch.

What does change is where the branch sits. Today the single-segment case is an
early return that decides the fan-out *and* the lane *and* repeats the
undecorate. After this change it decides the fan-out only:

```python
if len(segments) == 1:
    columns = [await _segment_column(segments[0][0], arr)]
else:
    columns = await asyncio.gather(*(_segment_column(payload, arr) for payload, _ in segments))
```

and the `len(columns) == 1` lane in Decision 1 handles the tuple-build question
separately. Two branches on two different questions, where there was one branch
answering both plus a duplicated tail.

### Decision 4: extract the present elements before the trial call

`_column()`'s three branches exist to carry `trial_i` — the index of the first
non-`None` element — through two comprehensions that must skip it (`i != trial_i`)
so the trial's own result is not recomputed. Extracting the non-`None` elements
into a list first makes the trial `results[0]`, and the bookkeeping has nothing
left to do:

```python
present = [element for element in arr if element is not None]
if not present:
    return [None] * len(arr)
if is_async_callable(extractor):
    return _interleave(arr, await asyncio.gather(*map(extractor, present)))
results = [extractor(element) for element in present]
if isawaitable(results[0]):
    return _interleave(arr, await asyncio.gather(*results))
return _interleave(arr, results)
```

**The call set is identical on every path**, which is the claim this decision
rests on. The sync-that-lied path looks like it changed and has not:
`asyncio.gather(trial, *(extractor(e) for ...))` already exhausts that generator
during argument unpacking, so every coroutine was created before anything was
awaited there too. The one-time `isawaitable` safety net still costs no extra
invocation, because the trial's coroutine still joins the gather rather than
being discarded.

The cost is one extra list of length n (`present`) on a function that already
builds two, against an O(n log n) sort — and `_column()` runs once per segment
per sort.

`_interleave(arr, values)` is the shared tail, and is a plain sync helper:

```python
def _interleave(arr: list[Any], values: list[Any]) -> list[Any]:
    it = iter(values)
    return [None if element is None else next(it) for element in arr]
```

**Alternative considered: extract `_interleave()` and leave the three branches
otherwise as they are.** That is roadmap **Next** item 3 read at its narrowest,
and it removes the three repetitions of the tail while keeping the `trial_i`
scan and both `i != trial_i` filters — the part that is actually hard to read.
Rejected as doing the easy half.

### Decision 5: no spec delta, and `comparator-contract` is the gate

Per proposal.md — Capabilities. The stability rule this change most plausibly
threatens is already specified, with scenarios: `reverse=True` must equal
comparator negation ties included, and equal-comparing elements must keep
encounter order. Decision 1 preserves both mechanisms rather than replacing
them, so the existing scenarios are the regression gate and the spec text
stands unaltered.

## Risks / Trade-offs

- **The mixed lane's generator is consumed by `zip()` inside `sorted()`, one
  level further from its `sorted()` than it is today.** → It was already a
  generator expression consumed by exactly one `zip`; nothing about single-pass
  consumption changes. Verified by `tests/test_comparing.py`'s mixed-direction
  scenarios, which are the only reachable path to that lane.
- **`all(directions)` is evaluated twice in the uniform lane** (once in the
  condition, once as `reverse`). → Over a tuple of at most a handful of bools,
  once per sort. Naming it a local would trade a line for a line.
- **A dropped branch can silently drop coverage.** → `sort-with-cmp-to-key`
  found exactly this. Compare the per-file coverage figure for `sort.py` before
  and after rather than accepting the `TOTAL` gate; an arm that became
  unreachable is a finding, not a saving.
- **The measured claims in `_sort_by_key()`'s docstring were made against the
  old structure.** → They are structural, not incidental (Decision 1), but the
  docstring must be re-read against the shipped code and its "single ascending
  segment ... takes today's exact path" sentence updated to name the lane rather
  than the early return.

## Migration Plan

Not applicable. One module, no public surface, no persisted state, no
deprecation window. Rollback is `git revert`.
