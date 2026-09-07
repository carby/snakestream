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
elements, interleaved round-robin, best of 3, median of 25 rounds, ns/element.
The prototype figures originally recorded here (−6.2%/−4.4% key segment,
−8.7%/−6.8% comparator segment, −3.5%/−1.9% two-segment chain, −20.3% async)
came from a version of `_segment_sign_sync`/`_segment_sign_async` with one
shared, unconditional null check after the branch that builds `ea`/`eb`. `ty`
rejected that shape - it cannot narrow `Any | None` through a compound
`nulls is not ABSENT and (...)` guard - and casting around it cost enough per
comparison to regress the sync shapes past the gate on measurement. What
shipped instead folds the null check into the nulls-tolerant branch itself
(see `_segment_sign_sync`'s docstring), which is what task 4.1 actually
measured, two independent runs:

| shape | sync delta |
|---|---|
| key segment | −10.4% / −8.7% |
| comparator segment | −11.3% / −10.4% |
| two-segment chain | −10.4% / −7.4% |

| shape | async delta |
|---|---|
| async extractor, one key segment | −11.0% / −6.4% |

The async prototype and shipped figures are not comparable to each other:
the prototype used a cheaper extractor than `bench_segment_sign.py`'s
`await asyncio.sleep(0)`, which dominates the per-element cost and dilutes
whatever the merge itself contributes (1147 ns/element baseline in the
prototype vs. 4346 ns/element here for nominally the same shape). Read
−8.7% as this change's own measurement, not as a regression from −20.3% -
the two numbers were never produced by the same harness running the same
code. Full figures: `baseline.txt` and `post_change.txt` in this change
directory.

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
