+++
id = "mark-to-map-order-blind"
title = "`to_map()` is marked order-blind (`mark-to-map-order-blind`)"
filed = 2026-08-31
closed = 2026-08-31
outcome = "shipped"
shipped_as = "mark-to-map-order-blind"
+++

**`mark-to-map-order-blind`** (2026-08-31) — closes the last of the seven
questions the **Open questions needing a session** section was opened to
carry, and **that section is now gone** rather than left standing empty; the
queue above it is where the next open item goes.

**The answer is two answers, because `to_map()` is two collectors behind one
factory.** Called without `merge_function` it declares
`Characteristics.UNORDERED`: the `dict` is a function of the element multiset
alone — each key and value comes from one element and consults no other,
`dict` equality ignores key order, and any multiset whose result would depend
on order raises instead. Called with one it declares nothing, **permanently**
and by written requirement rather than by silence, on the precedent
`mark-order-blind-collectors` set for `summing_double()`: `merge_function` is
caller-supplied and need not commute, and `lambda a, b: a` is the one-line
proof. It is the first factory here whose characteristics come from its
*arguments* rather than from its identity or a downstream's.

**The obstacle that kept it open did not survive contact with the contract.**
`mark-order-blind-collectors` declined to fold this in partly because the
no-merge form raises on a duplicate key and reordering can change which key
the message names. `UNORDERED` claims that two orderings collect to an equal
*result*, and an exception is not a result; what a caller can act on —
whether it raises, and the type — is order-invariant either way. Only the key
named varies, only with two or more distinct collisions, and only under
`RACING`, on a path where even the sequential answer was an artifact of
ordering rather than a documented choice.

**No benchmark was run, deliberately.** The barrier's cost is a property of
`race_through()` and not of the collector behind it, already measured at
1.12–1.27x on tail-latency IO. More per-element work in a collector makes the
barrier's relative cost *smaller*, so re-measuring with a dict-building
accumulator could only have weakened a case being made on semantics. This is
the shape of question that a benchmark cannot settle, which is exactly why the
section carried it separately from the parity queue.

**`to_map()` gets the stronger guard, not the weaker one.** `counting()` and
`to_set()` are verified by asserting the declaration plus the separately
pinned mechanism, because no public surface distinguishes their two paths. A
`dict` does: key iteration order follows insertion, so the order-blind path is
verified by *observation*, and the 3-arg form is verified from the other side
— a first-argument-winning merge must yield the encounter-order value. Both
were mutation-checked: marking both forms fails the second, marking neither
fails the first. `racing-encounter-order` gained the sentence that makes this
legible — a property the declaration does not *promise* is still admissible as
*evidence* of which path ran.
