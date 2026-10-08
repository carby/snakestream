+++
id = "segment-sign-sharing-cost"
title = "Sharing the segment-sign tail costs one frame, ~10-19ns"
filed = 2026-09-08
closed = 2026-09-09
outcome = "shipped"
shipped_as = "specialize-comparator-segments"
+++

**Sharing the segment-sign tail costs one frame, ~10-19ns** (closed
2026-09-09; filed 2026-09-08). Shipped as `specialize-comparator-segments`.

The question this item asked — can `_segment_sign_sync`/`_segment_sign_async`'s
shared six-line tail be de-duplicated for free — was answered by side
effect, and the answer inverts the item's own premise. Re-measurement
(`86acffe`) had already found the tail's cost to be a constant ~10-19ns per
segment per comparison rather than the ~3% the item was filed against, and
named the lead worth trying before accepting the cost: stop paying for the
frame rather than placing it better, by specializing each segment into a
closure at construction the way `callable-dispatch` already does for
awaitability.

That lead shipped. `KeyComparator.__init__` now builds `self._plan` — per
segment, an `(extract, compare, descending, is_async)` tuple whose `extract`
and `compare` halves are closures built once by `_build_extract`/
`_build_compare`. The sync/async twinning is confined to `extract`, the one
half that can await; `compare` is unconditionally sync and is therefore
written once and shared by both the sync and async per-comparison loops —
which is what the item asked for, structurally, because the shared tail no
longer sits behind the per-comparison `comparator is None` and `nulls is not
ABSENT` tests it used to; it replaces them.

**The tail became shareable, not singular.** Natural ordering and the
`type(sign) is not int` guard still each appear twice — once for the
intolerant leaf, once for the tolerant one — the same count as the baseline's
sync/async mirror, just moved onto a different axis: from two copies 60 lines
apart across an `async def` boundary to two copies inside one builder,
visible together. Collapsing them further was measured and declined a second
time: wrapping the intolerant leaf in a tolerant one costs the same frame
this item measured, on the tolerant path only, buying back exactly what the
extract/compare split spent.

Measured negative across nine per-comparison shapes (-4.4% to -19.2%, plan
vs. baseline, min and median agreeing, outside a null-test noise floor) and
positive on construction cost (+10.6% to +49.4%, paid once, break-even ~11
sync comparisons or ~5 async ones — every consumer of `__call__` performs
n-1 over a stream). Verified against a verbatim baseline across 26 comparator
shapes x 49 input pairs (1274 comparisons, sign and exception type both
checked) — zero mismatches. See `specialize-comparator-segments/
benchmark-findings.md` for both the prototype's figures and the shipped
shape's re-measurement, kept side by side rather than one overwriting the
other.
