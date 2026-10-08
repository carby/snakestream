+++
id = "order-racing-delivery"
title = "An ordered racing pipeline delivers in encounter order"
filed = 2026-08-28
closed = 2026-08-28
outcome = "shipped"
+++

**An ordered racing pipeline delivers in encounter order** (2026-08-28).
**BREAKING**, and the break is the point: `.parallel().map(f).collect(to_list())`
returned a scrambled list, which the guiding principle at the top of this file
classifies as a defect — Java's ordered parallel streams preserve encounter
order into `collect`, so "racing does not preserve encounter order" was the
rule that had to go, not the accidental in-order delivery behind a barrier.
The three things it settled, recorded because the reasoning took longer than
the code:
- **The barrier goes at `len(chain)`, not at index 0.** At index 0 the head is
  empty and the whole chain lands in the ordered tail — effectively
  sequential. At the end, every branch races the whole chain and only delivery
  is reordered, which is Java's shape and costs no per-element concurrency.
  `_split_point()` gained a third clause returning `len(chain)`, so one
  mechanism serves both callers and there is no second reorder implementation
  to keep in step.
- **A terminal declares whether it observes encounter order**, as
  `observes_order`, a bool passed to `_evaluate()` and through
  `Executor.value()`/`elements()`. `count()`, `for_each()`, `find_any()`,
  `max`/`min` and the `*_match` family declare `False` and pay nothing;
  `collect(collector)` reads the collector's `Characteristics.UNORDERED`,
  which is the first and only reader of what `add-collector-characteristics`
  shipped, and the reason that change existed.
- **`_resume_point()` was replaced, not tuned, and that is a concurrency
  *gain*.** It resumed racing only at an explicit `unordered()` because racing
  an order-blind suffix would scramble delivery; once delivery is reordered at
  the terminal that reason is gone. The barrier op runs one ordered pass and
  everything after it races. Measured: `.parallel().limit(8).map(50ms)` went
  **403.4 ms -> 101.7 ms**, the 4-branch floor exactly.

**The cost, measured, because the proposal required it before landing.**
Ordered delivery costs +33% per element (10.01 vs 7.51 us) on a 20,000-element
`map(x + 1)` — but that is a chain too cheap to race in the first place. On
40 elements at 10ms each, the shape racing exists for, ordered and
`unordered()` are 105.5 ms and 106.9 ms: within noise, and both 4x ahead of
sequential's 420 ms. So `unordered()` is measurably the faster path, as the
spec promises, and the default regression is charged where it does not matter.
Figures are in `race_through()`'s docstring.

**One latent bug fixed on the way.** `is_ordered()` folded from `True`
unconditionally, so the recursive re-entry over a chain *suffix* re-seeded the
fold and read `.sorted(c).unordered().limit(3)`'s suffix as ordered, installing
a barrier the caller had cleared two ops earlier. It now takes an `initial`
seed, threaded through `race_through(ordered_in=...)`.

Deliberately untouched, each with its own non-goal in the proposal:
`find_first()` and `for_each_ordered()` (that is **Next** item 2), marking the
collectors Java leaves unmarked, and exporting `_READ_AHEAD` (**Next** item 3,
whose answer this flips to "export it"). Four delta specs —
`racing-encounter-order` (2 added, 3 modified), `stream-execution-model`,
`stream-iterator`, `collector-protocol` — plus a README migration entry, the
CLAUDE.md ordering-barrier section, and a stale-`## Purpose` sweep over the
three capabilities whose framing the change falsified. 727 passed,
`--cov-fail-under=98` at 98.30%, `ruff`, `ruff format --check` and
`ty check src` clean. One existing test changed meaning:
`test_unordered_applies_only_to_ops_queued_after_it` asserted an in-order list
from `.limit(5).unordered()`, which was the accidental behaviour; it now
asserts the *selection* and lets delivery scramble, which is what the caller
declared. See `openspec/changes/archive/2026-08-28-order-racing-delivery`.
