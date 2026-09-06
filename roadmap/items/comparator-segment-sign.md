+++
id = "comparator-segment-sign"
title = "`comparator.py`'s segment-sign 2x2"
bucket = "next"
rank = 1
filed = 2026-09-02
claimed = 2026-09-02
updated = 2026-09-06
gate = "met in advance: must not regress past +10% ns/element (sync), measured negative in all six runs and -20.3% async"

[refs]
changes = ["merge-segment-sign-on-natural-ordering", "collapse-terminal-collector-duplication", "collapse-mutable-reduction-onto-collector"]
specs = ["comparator-key-comparator", "comparator-contract"]
files = ["src/snakestream/comparator.py", "src/snakestream/sort.py"]
+++

One of two duplications surfaced by the same read that produced
`collapse-mutable-reduction-onto-collector`, and deliberately left out of
`collapse-sort-decorate-lanes` rather than overlooked, because bundling it would
have put a measured trade-off inside a change that otherwise had none.

Scaffolded 2026-09-06 as `merge-segment-sign-on-natural-ordering` — proposal and
design written, tasks not, specs skipped. Still queue work: nothing is
implemented.

`_key_segment_sign_sync`, `_key_segment_sign_async`,
`_comparator_segment_sign_sync` and `_comparator_segment_sign_async` are one
function written four times. The shape underneath is that **a key segment is a
comparator segment whose comparator is natural ordering** — which
`comparator-key-comparator` already states as a requirement ("equivalent in
result to supplying a bare comparator that extracts both keys itself and
compares them"), so the merge makes a guaranteed equivalence structural rather
than maintained by hand in four places.

`.segments` keeps its shape regardless: `sort.py`'s `_segment_column()`
dispatches on `isinstance(payload, tuple)` to choose between a plain key column
compared in C and a `cmp_to_key`-wrapped one, and that is the
decorate-sort-undecorate fast path.

**The gate was met in advance, and the premise behind it was wrong.** It was
filed as a `+10%` ns/element ceiling to survive, on the assumption that merging
costs something on a per-element path (`min()`/`max()`, `min_by()`/`max_by()`,
one comparison per element) — `is_new_extremum`'s docstring records ~5% for
delegating a type check in the same neighbourhood. Measured on the
`collapse-terminal-collector-duplication` harness (20,000 elements, interleaved
round-robin, best of 3, median of 25 rounds, two independent runs), the merge
alone is noise; the merge **plus normalising the segment list once per
composition** is negative everywhere:

| shape | sync | async |
|---|---|---|
| key segment | −6.2% / −4.4% | |
| comparator segment | −8.7% / −6.8% | |
| two-segment chain | −3.5% / −1.9% | |
| async extractor, key segment | | **−20.3%**, ranges non-overlapping |

The refund comes from work `__init__` already knew and every comparison was
redoing: `isinstance(payload, tuple)` on both paths, and
`zip(self.segments, self._is_async, strict=True)` on the async one. That is the
same principle the class docstring already commits to — classification happens
"once here at construction rather than per element or per comparison" — applied
one step further, and it does not grow the object, since `_is_async`'s only two
uses were the `zip` and computing `_any_async`.

Behaviour is identical across 10 comparator shapes x 25 input pairs, covering
nulls, descending, chains, bare comparator segments and
`nulls_first()`/`nulls_last()`.
