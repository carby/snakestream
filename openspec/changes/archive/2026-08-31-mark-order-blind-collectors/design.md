## Context

See proposal.md — Why for the motivation and the measurements. The relevant
current state is that the mechanism this change depends on already exists and is
already guarded: `collect()` reads `Characteristics.UNORDERED` in one place, and
the `grouping_by`/`partitioning_by` recording tests fail if that read is lost.
This change adds *declarations*, not mechanism. No dispatch, executor or split
logic is touched.

## Goals / Non-Goals

**Goals**

- Add the mark to the collectors whose results are exactly order-invariant.
- State the floating-point exclusions as permanent, so the marking question
  cannot be reopened on them a fifth time.
- Give the barrier-skip a guard shape that survives refactors without anyone
  maintaining a benchmark.

**Non-Goals**

- `to_map()`. Item 4 raises it as a marking question because `to_map()` without
  a merge function raises on a duplicate key and reordering can change which key
  the message names, while a caller-supplied merge function need not commute.
  Both are real, both are separable from this change, and neither is settled by
  the benchmark that motivated it. Left open and explicitly not folded in.
- `min_by`/`max_by`. Already closed: `collector-min-max` requires them not to
  declare `UNORDERED`.
- Making the barrier itself cheaper. The tail-latency cost measured here is
  inherent to restoring order, not an inefficiency in how it is restored.
- Adding a performance test. See the decision below.

## Decisions

**Mark, rather than leave undeclared.** The three prior deferrals all rested on
the mark buying nothing where racing is legitimate. The tail-latency
measurements retire that reasoning: 1.12–1.27x on IO work with a realistic
latency distribution. Java's silence is the reason marking is *permitted*; the
measurement is the reason it is *worthwhile*. Alternative considered — declare
nothing, on the ground that the cheap-chain 1.33x optimizes a configuration
nobody should be in. That argument is sound and would have won on the original
evidence; it does not address the IO figure, which is the shape racing exists
for.

**Include `summarizing_int`/`summarizing_long`, which item 4 listed but the
benchmark did not cover.** `SummaryStatistics` is a `NamedTuple`, so `==` is
structural and the declaration is only as strong as its weakest field. Over
`int` inputs every field is exact: `min`/`max` select a value, not an element,
so unlike `min_by`/`max_by` there is no tie identity to preserve. Extending the
mark here is justified by that field-by-field argument rather than by the
benchmark, and the specs say so.

**State the floating-point exclusions as requirements rather than leaving them
silent.** An undeclared collector and a collector required never to declare are
indistinguishable in behaviour today, but not in what a later pass may do. These
are order-sensitive *in fact*, so writing the exclusion down converts a standing
invitation to re-examine them into a closed question. Alternative considered —
say nothing, since absence is already the default; rejected because item 4 has
been reopened three times, and silence is what allowed that.

**Guard by declaration plus mechanism, not by timing.** The natural instinct for
protecting a performance win is a performance test, and it is the wrong tool
here. The property is *which path ran*, and a wall-clock threshold is a proxy
for it that is both flaky under load and silently satisfiable by an unrelated
speedup. For the collectors this change marks, the direct observation used for
`grouping_by` is unavailable — `counting()` returns the same `int` either way —
so the guard decomposes the failure instead:

```
  refactor drops collect()'s read of characteristics
      -> recording-downstream tests fail        already pinned, untouched here
  refactor drops the mark from a factory
      -> declaration assertion fails            added by this change
```

Both are deterministic. Neither needs upkeep. Alternative considered —
instrument the accumulator to record arrival order; rejected because it would
test a hand-built collector rather than the shipped `counting()`, which is the
thing whose declaration is at risk.

**Write the guard rule down once, in `racing-encounter-order`.** The guard
itself already works — `to_set()`'s declaration is asserted, and the mechanism is
pinned elsewhere — so nothing here repairs a broken test. What is absent is any
statement of *why* that shape is the required one, which leaves a correctness-only
assertion looking sufficient to the next person who adds a marked collector. The
rule is stated in `racing-encounter-order` and referenced from the collector
capabilities rather than restated in each, because it is a property of how the
racing executor is verified, not of any one collector. `collector-to-set` gets
the one worked example, since a `set` is the case where the unavailability of
arrival-order observation is most obviously not a reason to settle for less.

## Risks / Trade-offs

**A caller reads `counting().characteristics` and finds it differs from
OpenJDK's `CH_ID`** → Characteristics are public surface, so this is a real
divergence in what is *reported*, even though nothing about the collected value
changes. Mitigated by the fact that Java's javadoc documents characteristics for
three factories only and is silent here, so there is no documented contract to
diverge from; the specs record that reasoning at the point of declaration rather
than leaving a future reader to rediscover it.

**The mark is wrong for a caller who was relying on encounter-order delivery
into one of these collectors** → Not possible to rely on for `counting()` or the
integer sums, whose results are identical either way. The exposure is confined
to collectors whose result could differ, and this change marks none of those.

**`summarizing_int` is marked on argument rather than measurement** → The
argument is field-by-field over exact integer arithmetic, and the specs require
a scenario asserting equality across all five fields, including `average`. If
that scenario fails, the mark is wrong and the failure is loud.

**The corrected docstring figures go stale the same way the originals did** →
Unavoidable for prose carrying numbers, and the reason the correction states the
*shape* that matters — uniform versus tail latency — alongside the figures, so a
future reader can tell what would have to be re-measured and why the original
benchmark could not have detected it.

## Migration Plan

None required. No public signature changes, no behaviour change under
`SEQUENTIAL`, and under `RACING` the marked collectors produce the same values
they did before, sooner. Rollback is removing the declarations.
