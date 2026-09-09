## Why

`KeyComparator.__call__` re-asks per comparison a set of questions that are
constant for the life of the comparator: is there an extractor, does this
segment await, does it pass `None` through, is there a supplied comparator.
`callable-dispatch` already establishes the opposite principle for awaitability
- classify once per composition, not per element - and `_norm`
(`merge-segment-sign-on-natural-ordering`) already took one step by hoisting
`isinstance(payload, tuple)` out of the per-comparison path. Taking the step to
its end measures **-10% to -20%** on every comparison `min()`, `max()`,
`min_by()` and `max_by()` make.

The immediate prompt is the roadmap item `segment-sign-sharing-cost`, which
asked whether the six-line tail `_segment_sign_sync` and `_segment_sign_async`
share can be de-duplicated. Re-measurement (commit `86acffe`) established that
sharing it behind one more call costs a constant ~10-19ns per segment per
comparison, at every denominator. This change stops paying for that frame
rather than placing it better: the tail's cost is absorbed because it *replaces*
the per-comparison `comparator is None` and `nulls is not ABSENT` tests instead
of sitting behind them.

## What Changes

- `KeyComparator.__init__` builds `self._plan` - per segment, an
  `(extract, compare, descending, is_async)` tuple whose first two members are
  closures specialized at construction - replacing `self._norm`, a tuple of raw
  data the per-comparison path had to re-branch on.
- Two builders replace four module-level helpers.
  `_build_extract(extractor, nulls, is_async)` returns the `(a, b) -> (ea, eb)`
  half; `_build_compare(comparator, nulls)` returns the `(ea, eb) -> sign` half.
  `_extract_pair_sync`, `_extract_pair_async`, `_segment_sign_sync` and
  `_segment_sign_async` are removed.
- `_compare_sync`/`_compare_async` become two-call loops: extract, compare,
  negate, short-circuit. The async loop calls a sync segment's closure directly
  rather than through a coroutine that awaits nothing.
- **The sync/async twinning is confined to the extractors** - the one part of a
  segment that can await. The tail stops being a sync/async mirror. It is *not*
  reduced to one copy: natural ordering and the `type(sign) is not int` guard
  each still appear twice, now split tolerant/intolerant inside one function
  rather than 60 lines apart across an `async def` boundary. That residue is
  accepted and recorded, not fixed - see design.md.
- Not a breaking change and not an API change. `Stream`, `sorted()`,
  `comparing()`, `then_comparing()`, `reversed()`, `nulls_first()`,
  `nulls_last()` and `.segments` all keep their current shapes and behaviour, so
  no README Migration entry is owed.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. Behaviour is identical: verified across 26 comparator shapes x 49 input
pairs (1274 comparisons) against a verbatim baseline, covering nulls first and
last, null *keys*, both-`None` ties, descending, reverse-before and
reverse-after chaining, bare comparator segments, contract violations and the
construction-time async-comparator rejection - zero mismatches. `comparator-
contract` and `comparator-null-ordering` state the rules this preserves; neither
changes. `.openspec.yaml` sets `skip_specs: true` accordingly.

## Impact

- **`src/snakestream/comparator.py` only.** Nothing outside it references
  `_norm`, `_segment_sign_sync`, `_segment_sign_async`, `_extract_pair_sync`,
  `_extract_pair_async`, `_compare_sync` or `_compare_async` - verified by grep
  across `src/` and `tests/`.
- `sort.py` is untouched. It reads `.segments` for its
  decorate-sort-undecorate column and never enters `__call__`, so `sorted()`
  neither gains nor loses from this.
- **Construction gets slower**: +388 to +910 ns per comparator built (+10% to
  +52%), since the closures are built there. Break-even is ~11 comparisons on a
  sync chain and ~5 on an async one; `min()`/`max()` perform n-1. Recorded as a
  deliberate trade in design.md.
- Gates: `ty` passes clean on the prototype. `ruff format` clean. One
  `ruff check` finding to resolve during implementation - `C901 _build_compare
  is too complex (11 > 10)`, the nested closures counting toward the function.
- Roadmap: closes `segment-sign-sharing-cost` by answering it, and the answer is
  not the one the item expected. That item's prose moves to `decisions.md`.
