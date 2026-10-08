+++
id = "java-8-parity-closed"
title = "Java 8 parity is closed"
filed = 2026-09-05
closed = 2026-09-05
outcome = "shipped"
+++

**Java 8 parity is closed** (2026-09-05) — the five gaps
`enumerate-java-8-parity-gaps` (2026-08-31) enumerated are all shipped, and
the **Now** entry queueing them is retired. This is the answer, not a status
update: there is no Java 8 parity gap left to point at, and the tables can be
re-counted in a minute (below) rather than re-argued.

| gap | closed by | when |
|---|---|---|
| `reduce(identity, accumulator, combiner)` | `3be5ed1`, `make-combiners-live` | 2026-09-05 |
| `to_map(key_mapper, value_mapper, merge_function, map_supplier)` | `f6406fe` | 2026-09-01 |
| `grouping_by(classifier, map_factory, downstream)` | `f6406fe` | 2026-09-01 |
| `nulls_first()` / `nulls_last()` | `8cdcf31` | 2026-09-01 |
| `comparing(f, keyComparator)` / `thenComparing(f, keyComparator)` | `31860e6` | 2026-09-01 |

The last row closed **past** parity rather than to it: both overloads were
struck-through *skips* at the time of the audit, decided against, and were
then implemented anyway. So the five-item list was the floor, not the ceiling.

**Counted, not asserted.** Every row in README's three tables is now either
`x` or struck-through; none is in the third state the audit introduced for a
genuine gap. Machine count at `3be5ed1`: `Stream` + `BaseStream` 37 / 11 / 0,
`Collectors` 24 / 3 / 0 (plus the `x/-` `Characteristics` row), `Comparator`
6 / 6 / 0 — 67 implemented, 20 skipped, **0 gaps**. The check is mechanical
because `enumerate-java-8-parity-gaps` made the tables *total over Java 8's
surface* and gave absence its own row state; that is what turns "are we done"
from a judgement into a `grep`. A Java 8 method with no row remains a defect
in the table, so a rediscovered gap is a documentation bug to fix in place,
not a reopening of this entry.

**Three documents disagreed with the code for four days** — the **Now**
queue, the Java 9 **Later** row, and the closing paragraphs of the audit's own
Done entry all still described five open gaps while four of them had shipped
by 2026-09-01. All three are corrected here: the two live pointers are
rewritten outright, and the Done entry keeps its text — it is history, and
accurate as of its date — with dated annotations marking in place the three
claims later events falsified. The lesson
is the one the audit itself drew one level up: a list of open items written in
prose decays the moment an item lands, which is exactly why the *table* —
with a row state for absence — is the artifact that answers this question,
and the roadmap is not.

**Java 9 is unaffected by this and stays in Later.** Closing Java 8 removes
the *gate* README put in front of Java 9; it does not supply the decision
that row is actually waiting on. See that row for the six additions and what
each would cost.
