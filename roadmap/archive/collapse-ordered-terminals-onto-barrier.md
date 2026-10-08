+++
id = "collapse-ordered-terminals-onto-barrier"
title = "`find_first()` and `for_each_ordered()` stop naming `SEQUENTIAL` and declare a demand"
filed = 2026-08-31
closed = 2026-08-31
outcome = "shipped"
shipped_as = "collapse-find-first-onto-barrier, collapse-for-each-ordered-onto-barrier"
+++

**`collapse-find-first-onto-barrier`** and
**`collapse-for-each-ordered-onto-barrier`** (2026-08-31) — item 2, landed as
two changes because the two terminals stopped sharing a fix once
`order-racing-delivery` shipped. Both had named `SEQUENTIAL` at their own call
site to buy encounter order; both now declare a demand and keep the caller's
executor. `for_each_ordered()` was a four-line deletion whose condition
`_split_point()` already computed. `find_first()` needed the terminal's
declaration widened from a bool to `OrderDemand` — `NONE`/`IF_ORDERED`/`ALWAYS`
— which makes clause 3 the two op clauses again one level up: `Ordering.SET`
is to `ALWAYS` what `order_sensitive` is to `IF_ORDERED`.

**The parity defect was that `find_first()` was a hidden mode switch**, the
only terminal that discarded `.parallel()` while `is_parallel()` still
reported `True`. Java's `FindTask` scans leftmost across fork-join branches;
it does not fall back to a sequential traversal. The guarantee never changed
and did not need to: the barrier restores encounter order on any chain,
because `_guarded()` assigns the source index under the lock and `unordered()`
clears the *requirement* to honour it, never the ability.

**Three corrections this item produced, each to something previously written
down as fact:**

- **`_is_ordered()` and the `SEQUENTIAL` name both survive.** The "what
  disappears" list claimed three deletions; it was one, `_evaluate()`'s
  `executor` parameter. `Stream.concat()` is `_is_ordered()`'s other caller
  and names `SEQUENTIAL` on the line above. The error had been copied here
  from `CLAUDE.md`, now fixed at both sites.
- **"racing wastes <=15 maps" had two regimes, and the common one is the
  worker count.** `find_first()` settles at the first *released group*, and no
  branch can be more than one group ahead by then, so a uniform-latency chain
  wastes `PROCESSES`. `_READ_AHEAD` is the bound only where element 0 is
  slower than what follows it. Measured: `filter`/`flat_map` 3.11x/3.21x, and
  `map` at 0.96x — **not a regression**, because the speculative maps run
  concurrently with the one that matters rather than in front of it.
- **The empty-chain `.parallel()` cost is not the barrier and is not new.**
  `count()` declares `NONE`, takes no split, and still pays almost all of it
  (1456us against `find_first()`'s 133us on 200 elements), so it is
  `race_through()`'s branch-setup cost and has been there since delivery
  ordering landed. Recorded in `race_through()`'s docstring; no fast path,
  because a barrier-keyed one would fix nothing.

Two silent breaks, both in README's migration log: `find_first()` stops
overriding `unordered()` for an order-sensitive op upstream, and a chain
callable may run for more than one element. `.sequential()` restores both.
Also deleted a `terminal-sinks` scenario asserting an unordered parallel
`find_first()` "behaves as `find_any()`", which had contradicted
`stream-find-first` and the shipped code since
`order-stateful-ops-under-racing`.
