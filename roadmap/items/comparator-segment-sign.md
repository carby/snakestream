+++
id = "comparator-segment-sign"
title = "`comparator.py`'s segment-sign 2x2"
bucket = "next"
rank = 1
filed = 2026-09-02
claimed = 2026-09-02
gate = "per-element path: +10% ns/element (sync variant), per `collapse-terminal-collector-duplication`"

[refs]
changes = ["collapse-terminal-collector-duplication", "collapse-mutable-reduction-onto-collector"]
specs = ["comparator-key-comparator", "comparator-contract"]
files = ["src/snakestream/comparator.py", "src/snakestream/sort.py"]
+++

One of two duplications surfaced by the same read that produced
`collapse-mutable-reduction-onto-collector` (scaffolded the same day, and
deliberately not filed here — it has its own change directory). Both were
passed over for that one because it was the only candidate whose per-element
path is provably unchanged; each of these needs a measurement the collapse did
not. This is the more valuable of the two.

`_key_segment_sign_sync`, `_key_segment_sign_async`,
`_comparator_segment_sign_sync` and `_comparator_segment_sign_async` are one
function written four times: the natural-ordering expression
`(ka > kb) - (ka < kb)` appears in all four, and so does the null-tie clause
`0 if <a> is None and <b> is None else _null_sign(...)`. The shape underneath is
that **a key segment is a comparator segment whose comparator is natural
ordering** — which is the unification, and also the reason it cannot be done by
normalising the payload: `sort.py`'s `_segment_column()` dispatches on
`isinstance(payload, tuple)` to choose between a plain key column (compared in
C) and a `cmp_to_key`-wrapped one, and that distinction is the
decorate-sort-undecorate fast path. So the payload shapes stay and only the
sign functions merge.

*The gate.* These four are reached only through `KeyComparator.__call__`, which
`sort()` never uses — it unwraps `.segments` instead. The live consumers are
`min()`/`max()` and `min_by()`/`max_by()`, at one comparison per element. That
is a per-element path, which is where every measured rejection in
[`decisions.md`](../decisions.md) has happened, so the
`collapse-terminal-collector-duplication` threshold (+10% ns/element, sync
variant) applies unchanged. `is_new_extremum`'s own docstring already records
what this neighbourhood costs: delegating its type check measured ~5%.
