# Extract the racing branches' task lifecycle

## Why

`execution.py` names four primitives in its module docstring — `stream_through()`,
`race_through()`, `feed_through()`, `drain()`. There is a fifth, and it has no
name because it was copied rather than extracted: the `FIRST_COMPLETED` merge
over N branches' `anext()`, which appears verbatim at `execution.py:399-433`
(`_release_in_order`) and `execution.py:603-623` (`race_through`).

Twenty lines are identical between the two — arming one task per branch,
`asyncio.wait(..., FIRST_COMPLETED)`, popping the completed task, swallowing
`StopAsyncIteration`, re-arming, and cancelling plus gathering the leftovers on
the way out. Both docstrings already admit it in prose. `_release_in_order`
opens with "the reorder barrier: **the same `FIRST_COMPLETED` merge
`race_through()` runs**, with a buffer in front of the yield", and its `finally`
is commented "same clean-up as `race_through()`'s, plus closing the branches".
Those two sentences are a function signature written as a comment.

The duplication also hides an asymmetry rather than stating it:
`_release_in_order` closes its branches explicitly and `race_through` does not,
and nothing says whether that is a windowed-path necessity or an oversight.

## What Changes

- Extract the **arming and the cleanup** of the per-branch `anext()` tasks into
  one `@asynccontextmanager` in `execution.py`, alongside `_maybe_aclosing()`,
  which is the same pattern one screen up in the same file. Both callers enter
  it and keep their own loop body.
- Unify the cleanup: **both** paths close their branches, not just the
  windowed one. This conforms to an existing requirement rather than changing
  one — see Impact.
- No change to `_release_in_order`'s signature; `tests/test_racing_encounter_order.py:669`
  calls it directly and keeps working untouched.
- **Not taken: extracting the whole loop as a `merge()` async generator.** It
  removes eight further lines and costs ~4% per element on the racing path. See
  design.md, which carries the measurement.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. This is a pure refactor: same elements, same order, same close counts,
same public surface. `.openspec.yaml` sets `skip_specs: true` accordingly —
the same posture `sort-with-cmp-to-key` took for a change that was measurable
but not observable.

The branch-closing unification is deliberately *not* a spec change.
`racing-encounter-order` already requires that "the shared source SHALL be
closed exactly as it is without a barrier ... and a delivery barrier SHALL NOT
change it either", with two scenarios asserting the close counts are equal
across the two paths. Making both paths close their branches is that
requirement being met by one mechanism instead of two, so the spec text stands
unaltered and its existing scenarios are the regression gate.

## Impact

- `src/snakestream/execution.py` only. One new private helper; two call sites
  shortened. Nothing else in `src/` imports the affected lines.
- No test changes, including imports: every name the suite reaches for
  (`_release_in_order`, `_guarded`, `_Window`, `_in_flight`, `race_through`)
  keeps its name and signature.
- No migration-log entry. Nothing a caller can observe changes, and that
  absence is a claim rather than an oversight.
- `CLAUDE.md`'s architecture section lists the execution primitives; the new
  helper is scaffolding around them rather than a fifth primitive, so that list
  is unchanged. The module docstring gains a clause naming the shared lifecycle.
