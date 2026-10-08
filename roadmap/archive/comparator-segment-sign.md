+++
id = "comparator-segment-sign"
title = "`comparator.py`'s segment-sign 2x2"
filed = 2026-09-02
closed = 2026-09-07
outcome = "shipped"
shipped_as = "merge-segment-sign-on-natural-ordering"
+++

**`comparator.py`'s segment-sign 2x2** (closed 2026-09-07; filed 2026-09-02).
Shipped as `merge-segment-sign-on-natural-ordering`.

`_key_segment_sign_sync`, `_key_segment_sign_async`,
`_comparator_segment_sign_sync` and `_comparator_segment_sign_async` were one
function written four times. The shape underneath is that **a key segment is
a comparator segment whose comparator is natural ordering** —
`comparator-key-comparator` already states as much as a requirement
("equivalent in result to supplying a bare comparator that extracts both
keys itself and compares them"), so the merge made a guaranteed equivalence
structural rather than maintained by hand in four places. The two survivors,
`_segment_sign_sync`/`_segment_sign_async`, take `extractor` and `comparator`
as separate optional parameters; `comparator is None` selects natural
ordering and returns before the `type(sign) is not int` guard, since only a
user-supplied comparator can fail it. `KeyComparator.__init__` now also
precomputes `self._norm` — a tuple of `(extractor, comparator_or_None,
descending, is_async)` per segment — so `isinstance(payload, tuple)` and
`zip(self.segments, self._is_async, strict=True)` stop running per
comparison; `.segments` and `sort.py` are untouched, since `.segments`
is what `sort.py`'s `_segment_column()` reads for its
decorate-sort-undecorate fast path and `_norm` is a derived view only
`__call__` reads.

**The gate was met in advance, and the premise behind it was wrong.** It was
filed as a `+10%` ns/element ceiling to survive, on the assumption that
merging costs something on a per-element path (`min()`/`max()`,
`min_by()`/`max_by()`, one comparison per element). Measured on the
`collapse-terminal-collector-duplication` harness (20,000 elements,
interleaved round-robin, best of 3, median of 25 rounds, two independent
runs), the shipped merge plus normalisation is negative everywhere: key
segment −10.4%/−8.7%, comparator segment −11.3%/−10.4%, two-segment chain
−10.4%/−7.4%, async key segment −11.0%/−6.4%.

**A prototype shape reached for a larger win and lost it to the type
checker.** An earlier version shared one null check unconditionally after
building `ea`/`eb`, gating it with `nulls is not ABSENT and (ea is None or
eb is None)`. `ty` could not narrow `Any | None` through that compound
condition, and casting around it on every read of `ea`/`eb` cost enough per
comparison to push the *sync* shapes past the +10% gate on measurement — the
opposite of the change's purpose. The shipped shape instead folds the null
check into the nulls-tolerant branch itself (`_segment_sign_sync`'s
docstring in the archived change), which the type checker narrows for free
and which measures negative on all eight runs above. The prototype's
headline figures (including a −20.3% async number) are not comparable to
what shipped: they were also measured on a cheaper async extractor than
`bench_segment_sign.py` ships with today, which dominates the async
shape's per-element cost enough to dilute whatever the merge itself
contributes. Anyone re-deriving this number should use the archived
change's `post_change.txt`, not the proposal's original table, which a
peer review caught still asserting the prototype figures as fact after
the shape changed — see the archived change's `proposal.md` Why and
`openspec/changes/archive/2026-09-07-merge-segment-sign-on-natural-ordering/`
for the full record.

Behaviour is identical across 10 comparator shapes x 25 input pairs,
covering nulls, descending, chains, bare comparator segments and
`nulls_first()`/`nulls_last()`.
