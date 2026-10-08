+++
id = "define-unordered-as-equality"
title = "`Characteristics.UNORDERED` gets one definition (`define-unordered-as-equality`)"
filed = 2026-08-28
closed = 2026-08-28
outcome = "shipped"
shipped_as = "define-unordered-as-equality"
+++

**`define-unordered-as-equality`** (2026-08-28) — `Characteristics.UNORDERED`
now has one definition instead of two. It promises `==`-equality of the
collected result and **nothing** about that result's iteration order, stated
in the `Characteristics` docstring and in `collector-protocol` rather than
inferred from the word "equal". The stricter reading that lived in two source
comments — that nothing observable may differ — is withdrawn: a CPython `set`
built from the same members in two orders is `==` while iterating
differently, so the strict rule was both false in its premise and fatal to
`to_set()`, its only declarer.

Two consequences. `to_set()`'s justification is repaired — the requirement is
unchanged, the reason for it is now set equality rather than the false
structural claim. And `grouping_by()`/`partitioning_by()` **derive**
`UNORDERED` from their downstream, the same one keyword `mapping()` and
`collecting_and_then()` already used, on separate reasoning each:
`dict.__eq__` is key-order-insensitive and the classifier is a function of
the element, versus both partitions being seeded in the supplier. Nothing in
`execution.py`, `_split_point()` or the barrier changed — only what two
factories report to `collect()`.

Silent break, recorded in README's migration log: on an ordered racing
pipeline these two with an order-blind downstream no longer take the delivery
barrier, so the returned mapping's key iteration order stops being
deterministic. The value is unchanged under `==`; `.sequential()` or an
order-observing downstream restores the order.

This settles the **derivation** half of **Now** open question 4. The marking
half — whether `counting()`, `summing_int/long()` and `summarizing_int/long()`
should *declare* it — is still open and still owes a benchmark, and the float
family plus `to_map(..., merge)` are recorded there as permanently unmarkable.
