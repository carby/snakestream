+++
id = "mark-order-blind-collectors"
title = "Counting and integer-summing collectors are marked order-blind (`mark-order-blind-collectors`)"
filed = 2026-08-31
closed = 2026-08-31
outcome = "shipped"
shipped_as = "mark-order-blind-collectors"
+++

**`mark-order-blind-collectors`** (2026-08-31) — `counting()`,
`summing_int()`/`summing_long()` and `summarizing_int()`/`summarizing_long()`
declare `UNORDERED`, so they skip the racing delivery barrier. Nothing
observable changes — each returns a value identical under either delivery
order, which is what makes the declaration truthful — and the reason to make
it is a cost the previous benchmark could not see. `race_through()`'s "nothing
at all on IO-bound work" came from 40 elements at a **uniform** 10ms, where
the reorder buffer never holds an element back; under tail latency (200
elements, 90% at 2ms and 10% at 50ms) the barrier costs 1.12x, and with a
periodic straggler 1.27x. The docstring now carries both shapes and says which
one a uniform benchmark cannot measure.

The floating-point family is excluded **permanently and in writing** rather
than left undeclared: `summing_double()`, `averaging_*()` and
`summarizing_double()` are order-*sensitive in fact*, float addition not being
associative, and `summarizing_double()` sharpens it — one order-sensitive
field makes the whole `NamedTuple` compare unequal however exact the fields
beside it are. Item 4 had been reopened three times; silence is what allowed
that, so the exclusions are now requirements.

`_summing()` and `_summarizing()` take the mark as a per-caller parameter
rather than deriving it from their `coerce` argument, which happens to agree
today: sharing a body must not let `summing_double()` inherit
`summing_int()`'s declaration.

**Two claims made while proposing this were wrong and were corrected before
implementing.** The change was pitched partly on `to_set()`'s barrier-skip
being "guarded by nothing"; the test asserts the declaration and fails when it
is removed, verified by hand. What was missing was the rule, not the guard —
`racing-encounter-order` now states that a correctness-only assertion cannot
discharge an order-blind scenario, that observation of arrival order is the
method wherever the result permits it, and that timing must never be, because
the property under test is which path ran and not how fast it ran. `to_map()`
is left open, and item 5 says why it is not a parity gap.
