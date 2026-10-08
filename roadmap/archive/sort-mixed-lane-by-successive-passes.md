+++
id = "sort-mixed-lane-by-successive-passes"
title = "The mixed-direction sort lane becomes successive stable passes (`sort-mixed-lane-by-successive-passes`)"
filed = 2026-09-02
closed = 2026-09-02
outcome = "shipped"
shipped_as = "sort-mixed-lane-by-successive-passes"
+++

**`sort-mixed-lane-by-successive-passes`** (2026-09-02) — `_sort_by_key()`'s
mixed-direction lane was the only place left in the sort where a comparison
ran in Python rather than in C: a chain whose segments disagreed on direction
wrapped its descending columns in `_Descending`, whose `__lt__` cost a Python
frame once per pair the earlier columns tied on. CPython's own guarantee
removes the wrapper — sorts are stable, `reverse=True` included, so a series
of stable passes least-significant-column-first *is* a lexicographic ordering
with a direction per column. Three lanes collapsed to one loop, `_Descending`
was deleted, and every comparison returned to C.

*The gate was met, in advance*, and this one was not the usual shape: the
measurement was banked in the change's design.md, and the per-element path
got *cheaper* rather than being asked to absorb an abstraction. 20,000 rows,
best of 11, output asserted element-identical including tie order — mixed
**6.8x / 4.9x / 4.5x** at k=2/4/8, uniform **1.39x / 1.22x** at k=2/3. Also
measured on distinct-key input, where the tuple lanes short-circuit at their
best: mixed still 3.45x / 2.66x. Reproduced on the shipping machine at a lower
magnitude but the same shape — mixed 6.0x/3.83x/2.81x, uniform crossover
still between k=4 and k=5 — machine-to-machine variance, not a regression
from the design's figures.

*What it costs, and where.* Uniform chains cross over between four and five
segments — **0.93x at k=5, 0.68x at k=8** — because k passes of C comparison
eventually lose to one short-circuiting tuple comparison. Taken deliberately
(design.md Decision 2): confining the rewrite to the mixed lane would have
been faster on long uniform chains but would have made an *observable*
behaviour lane-dependent, since sorting every column in full is what makes a
segment's incomparable keys raise unconditionally rather than only where an
earlier segment ties. One path, one rule. It carries the one behavioural
delta in the change — `comparator-chaining`'s "Keys within a segment must be
mutually comparable" strengthened to make the raise unconditional, synced to
the main spec at archive — so unlike its neighbours here it was not
`skip_specs`.
