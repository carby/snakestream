## Why

`comparator.py` computes one segment's sign four times:
`_key_segment_sign_sync`, `_key_segment_sign_async`,
`_comparator_segment_sign_sync` and `_comparator_segment_sign_async`. The
natural-ordering expression `(ka > kb) - (ka < kb)` appears in all four; so does
the null-tie clause `0 if <a> is None and <b> is None else _null_sign(...)`.

The shape underneath is that **a key segment is a comparator segment whose
comparator is natural ordering**, which the `comparator-key-comparator` spec
already asserts as a requirement rather than an implementation detail:

> Both SHALL be equivalent in result to supplying a bare comparator that
> extracts both keys itself and compares them.

So the merge does not invent an equivalence; it makes one the spec already
guarantees structural instead of coincidental, and removes the risk that four
copies drift apart while the requirement says they may not.

**The measurement inverts the item's premise.** The roadmap filed this behind a
`+10%` ns/element ceiling on the assumption that merging costs something on a
per-element path (`min()`/`max()`, `min_by()`/`max_by()`, one comparison per
element). It does not cost — it refunds, once the merge is paired with
normalising the segment list once per composition rather than re-deriving it on
every comparison.

## What Changes

- The four sign functions become two, `_segment_sign_sync` and
  `_segment_sign_async`, each taking an extractor and a comparator. A
  `comparator is None` branch selects natural ordering; the
  `ComparatorContractException` type check stays on the supplied-comparator
  path only, where it belongs, and natural ordering never reaches it.
- `KeyComparator.__init__` precomputes `self._norm`, a tuple of
  `(extractor, comparator_or_None, descending, is_async)` per segment.
  `_compare_sync` and `_compare_async` iterate that directly, so
  `isinstance(payload, tuple)` and `zip(self.segments, self._is_async,
  strict=True)` stop running per comparison.
- `self._is_async` becomes a local in `__init__`, since its only two uses were
  computing `_any_async` and that `zip`. The object's field count is unchanged:
  `segments` + `_norm` + `_any_async` replaces `segments` + `_is_async` +
  `_any_async`.
- `self.segments` is untouched in shape and meaning.

Measured on the `collapse-terminal-collector-duplication` harness — 20,000
elements, interleaved round-robin, best of 3, median of 25 rounds, ns/element,
two independent runs:

| shape | sync delta |
|---|---|
| key segment | −6.2% / −4.4% |
| comparator segment | −8.7% / −6.8% |
| two-segment chain | −3.5% / −1.9% |

| shape | async delta |
|---|---|
| async extractor, one key segment | **−20.3%** (1147.2 -> 913.8 ns/element, ranges 1088-1168 vs 874-936, non-overlapping) |

Behaviour is identical across 10 comparator shapes × 25 input pairs, covering
nulls, descending, chains, bare comparator segments and
`nulls_first()`/`nulls_last()`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. `comparator-key-comparator` and `comparator-contract` describe results —
which ordering wins, what a non-`int` comparator result raises — and every one
of their requirements holds unchanged, verified by the equivalence check above.
The change is internal structure plus a measured speedup, so it sets
`skip_specs: true` rather than inventing a requirement.

## Impact

- `src/snakestream/comparator.py` — four functions become two;
  `KeyComparator.__init__`, `_compare_sync` and `_compare_async` change.
- `src/snakestream/sort.py` — **not** changed, and that absence is the point.
  `_segment_column()` dispatches on `isinstance(payload, tuple)` to choose
  between a plain key column compared in C and a `cmp_to_key`-wrapped one,
  which is the decorate-sort-undecorate fast path. `.segments` keeps its shape
  precisely so that stays true; `_norm` is a derived view `__call__` reads and
  `sort()` never does.
- `tests/` — no behavioural test should need editing. A test naming a removed
  function by name follows the merge.
- Not in scope: the sync/async split, which stays 1x2. `add-callsite-dispatch`
  closed unifying that axis and `decisions.md` records it re-declined a fourth
  time on 2026-09-03.
