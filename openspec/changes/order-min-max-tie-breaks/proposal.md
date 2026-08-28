## Why

`comparator-contract` requires that `min()` and `max()` retain the
**earlier-encountered** of two elements that compare equal. Under the racing
executor they retain the earlier-*arriving* one instead: `_min_max()` declares
`observes_order=False`, so no delivery barrier is engaged and which of two
equal-comparing but distinguishable elements is returned is arbitrary. This is
not a gap in the specification — it is an existing requirement the racing path
violates, covered only by sequential scenarios.

The same rule already behaves differently through the collector form.
`min_by()`/`max_by()` declare no `Characteristics.UNORDERED`, so
`collect(max_by(c))` takes the barrier and *is* deterministic, while
`.parallel().max(c)` is not. `is_new_extremum()` calls itself "the one home for
the rule `Stream.min()`/`max()` and the `min_by()`/`max_by()` collectors both
implement"; today the two callers give different answers on a tie.

The divergence is observable exactly where a comparator is a partial key over
richer objects — `.parallel().max(comparing(lambda e: e.score))` over records
with tied scores — which is the mainstream use of `comparing()`, not a corner.

## What Changes

- `Stream.min()`/`max()` declare that they observe encounter order, so an
  **ordered** racing pipeline delivers to them behind the existing reorder
  barrier and the first of tied elements in encounter order wins, matching
  Java's parallel `minBy`/`maxBy` and the sequential result. One argument in
  `_min_max()`; no new machinery.
- **BREAKING (silent, safe direction):** `.parallel().max(c)`/`.min(c)` on an
  ordered pipeline now return a deterministic element on a tie where they
  previously returned an arbitrary one. The value is unchanged whenever the
  comparator is consistent with equality; only tie *identity* changes, and it
  changes to match the sequential answer. Racing `min()`/`max()` on a chain too
  cheap to race now pays the delivery barrier it previously skipped;
  `unordered()` restores the old behaviour and cost exactly.
- Ties on a pipeline declared `unordered()` stay arbitrary and are specified as
  such, matching Java, where an unordered parallel `min()` may break ties any
  way. `then_comparing()` is the documented lever for callers who want a
  determinate answer without a barrier.
- `min_by()`/`max_by()` are specified as never declaring
  `Characteristics.UNORDERED`, so the collector form keeps the behaviour it
  already has and the two forms stay converged. This settles the exclusion
  `collectors.py` currently states in a comment.
- `sorted()`'s **stability** is specified for the first time, sequentially and
  under racing. It holds today — `Ordering.SET` splits unconditionally so the
  sort sees the whole stream in encounter order, and all three sort algorithms
  are stable — but nothing states or tests it, and `racing-encounter-order`
  currently asserts the opposite in passing.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `comparator-contract`: the "keep the first of tied elements" requirement is
  narrowed to ordered pipelines and gains racing and `unordered()` scenarios; a
  new requirement states `sorted()`'s stability, so one capability owns what
  happens to tied elements for all three comparator-consuming operations.
- `racing-encounter-order`: `max()` and `min()` move from the list of terminals
  that do NOT observe encounter order into the list that does. The statement
  that on an unordered pipeline "a sort's output carries no cross-branch
  ordering guarantee" is corrected — `_split_point`'s first clause fires on
  `Ordering.SET` regardless of the ordering characteristic, so
  `.unordered().sorted()` does see the whole stream.
- `collector-min-max`: gains a requirement that these two collectors do not
  declare `UNORDERED`, and that their tie-break is therefore encounter-order.

## Impact

- `src/snakestream/stream.py` — `_min_max()`'s `observes_order` argument and the
  comment above it, which currently records the superseded reasoning.
- `src/snakestream/comparator.py`, `src/snakestream/collectors.py` — the
  docstring and comment asserting the shared-rule claim become true again and
  should say so.
- No change to `execution.py`: this uses `_split_point`'s existing terminal
  clause. No new executor, no new sink protocol, no protocol change on
  `Executor`.
- `README.md` — the `max()`/`min()` rows, the `parallel()` row (which lists
  `max()`/`min()` among the terminals that "pay nothing either way"), and a
  migration-log entry.
- `roadmap.md` — closes open question 3, and removes `min_by`/`max_by` from
  question 4's scope for a stated reason.
