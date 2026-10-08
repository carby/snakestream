+++
id = "order-min-max-tie-breaks"
title = "Parallel `min()`/`max()` break ties in encounter order (`order-min-max-tie-breaks`)"
filed = 2026-08-28
closed = 2026-08-28
outcome = "shipped"
shipped_as = "order-min-max-tie-breaks"
+++

**`order-min-max-tie-breaks`** (2026-08-28) — `.parallel().min()`/`.max()`
now break ties in encounter order, resolving **Now** open question 3.
`_min_max()` declares `observes_order=True` and takes the existing terminal
clause in `_split_point()`; nothing in `execution.py` changed. Ties on a
pipeline declared `unordered()` stay unspecified, matching Java, with
`then_comparing()` as the lever for a caller who wants determinism without
the barrier.

Two facts found while writing it are why the "spec ties as unspecified"
option was never really open. `comparator-contract` **already required**
first-of-tied-in-encounter-order, so racing was violating an existing
requirement rather than filling a gap; and `Stream.min()` and
`collect(min_by(c))` **disagreed with each other**, the collectors having
taken the barrier all along. The cost objection did not survive either:
`sorted()` has always paid *more* for the same kind of determinism, splitting
at its own index where `min`/`max` split at `len(chain)`.

Two things landed alongside. `sorted()`'s **stability** is specified and
tested for the first time — it held already, but nothing said so, and
`racing-encounter-order` asserted the opposite in passing for the
`unordered()` case, which is corrected. And `collector-min-max` now
*requires* `min_by`/`max_by` not to declare `UNORDERED`, which takes them out
of open question 4 permanently instead of by convention.
