+++
id = "terminals-onto-collectors"
title = "Measured and rejected: collapsing `min`/`max`, `count` and `reduce` onto their collectors"
filed = 2026-08-21
closed = 2026-08-21
outcome = "declined"
+++

**Measured and rejected: collapsing `Stream.min`/`max`, `count` and `reduce`
onto the `min_by`/`max_by`, `counting()` and `reducing()` collectors.**
The duplication was real — `_MinMaxSink` and `_extremum` were the same
algorithm down to a verbatim copy of the comparator-contract comment,
`_CountSink` and `counting()` the same `+= 1`, `_ReduceSink` and
`reducing()`'s two-arg form the same `_UNSET`-seed fold — and the collapse
was implemented in full to find out what it cost.

**Equivalence is not in doubt**, which is what makes the rejection a pure
cost decision. With all three terminals routed through `collect(...)` and
the three sinks deleted, the **whole 505-test suite passed with no test file
edited**, and a separate 21-case audit (empty sources, singletons, falsy
identities, first-of-tied tie-break, the `bool`-comparator `TypeError`, async
callables, and all three on a `ParallelStream`) found **zero** differences
between the two forms.

**Killed on measurement at the gate the change's own tasks placed after the
collapse.** Both forms are public API today, so baseline and collapsed ran
interleaved in one process against the same source — a tighter comparison
than the usual edit-and-remeasure. Harness otherwise as established (Python
3.14.5, 20,000 elements, best of 5, three independent invocations), with one
deliberate change: **no intermediate chain**, since here the terminal is the
subject and an empty chain maximizes its share of per-element cost. Gate was
+10% on the sync variant, the level `collapse-terminal-drive-loop` already
treated as real:

| Variant | Baseline ns/element | Collapsed ns/element | Median delta |
|---|---|---|---|
| `count()` | 298 / 306 / 299 | 360 / 332 / 357 | **+19.6%** |
| `min(cmp)` sync | 467 / 442 / 422 | 608 / 560 / 522 | **+26.5%** |
| `min(cmp)` async | 558 / 551 / 513 | 648 / 626 / 651 | +16.2% |
| `reduce(acc)` sync | 332 / 356 / 354 | 622 / 562 / 601 | **+69.6%** |
| `reduce(0, acc)` sync | 369 / 331 / 355 | 630 / 590 / 601 | **+70.6%** |
| `reduce(acc)` async | 454 / 468 / 466 | 657 / 720 / 714 | +53.3% |

All three failed, so all three took the fallback. The cause is the same one
`add-callsite-dispatch` established: a `Collector` must be reusable across
concurrent collections, so its per-collection dispatch state lives on a
supplier-made box reached through a Python-level `async def` call, where a
sink has it inline on `self`. `reduce` is worst by a wide margin because
`reducing()` additionally routes every element through `_classify_step`,
which is a function call plus a tuple allocation and unpack per element per
callable — precisely the cost `optimize-callable-dispatch` hoisted out of the
per-element path in the first place.

**What landed instead — the per-terminal fallbacks, all behaviour-neutral,
505 tests passing unedited at 98.20% coverage:**

- **`min`/`max`: the shared rule was extracted, and it made both sides
  faster.** `sort.py` gained `is_new_extremum(sign, asc)`, holding the
  comparator-contract check, the sign test and the first-of-tied rule — the
  part that had been duplicated verbatim — called by both `_MinMaxSink` and
  `_extremum`. It *replaces* their existing `check_comparator_result_type()`
  call rather than adding a second one, and inlines the `type(sign) is not
  int` test so only the raising path calls out. Net one fewer Python-level
  call per element: `min` sync went **442 -> 404 ns/element**. (Delegating to
  `check_comparator_result_type` instead of inlining the test measured ~5%
  slower, which is why it does not.)
- **`count`: roadmap item 2(c) taken as the fallback.** `_CountSink` now
  accumulates into a plain `int` instead of a `Counter` box, since the sink
  owns its container exclusively — 300 vs 299 ns/element, i.e. neutral on
  time, with one allocation and one indirection gone. `counting()` keeps its
  box, which it genuinely needs: its accumulator is a free function that has
  to mutate a container it was handed. `Counter` itself stays regardless —
  `ops.py`'s `_LimitOp` and `_SkipOp` use it as state shared across a
  `ParallelStream`'s branches, the case a plain `int` cannot serve.
- **`reduce`: cross-referenced, not merged.** The shared part is the
  `_UNSET`-seed rule and the empty-finishes-as-`None` rule — two lines and a
  comment, not an extractable function. `_ReduceSink`'s docstring and
  `reducing()` now each point at the other, recording that the duplication is
  deliberate and measured and that a change to either rule belongs in both.

**Consequence:** routing these terminals through a `Collector` is now a
deliberately-accepted cost with numbers behind it rather than an open cleanup
item, and should not be re-proposed without new evidence — the same posture
`add-callsite-dispatch` established. The narrower reading that *did* pay off
is worth keeping in mind: extracting a **sync** helper that replaces an
existing per-element call is free or better, while anything adding a
coroutine frame or a box to the per-element path is not. `stream.py` is
untouched; `README.md` changed only in the `min_by`/`max_by` rows, whose
"Wraps `Stream.min()`'s existing logic" wording is now "shares the rule
with", which is what the code actually does. See
`openspec/changes/collapse-terminal-collector-duplication`.
