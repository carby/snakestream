## Context

See `proposal.md` — Why. The design-relevant facts about the current code:

- `_CollectorSink` (`collector.py:63-92`) already **is** a `TerminalSink`. It
  classifies `collector.accumulator` through `AsyncDispatch` and calls
  `supplier()` from `_create_container()`, `finisher()` from `_finish()`. It is
  built fresh per `collect()` call, so no classification state leaks between
  compositions or across a `ParallelStream`'s branches.
- The three collector factories the terminals would fold onto keep their
  per-collection dispatch state on a **supplier-made box** (`_ExtremumBox`,
  `_ReduceBox`, `Counter`) rather than on the sink, because a `Collector` is
  reusable across concurrent collections. The three terminal sinks keep the
  same state on the sink itself, via `AsyncDispatch`.
- That box is the whole cost difference. Per element, the sink path is
  `self._fn(...)` plus two attribute loads on `self`; the collector path is a
  Python-level `async def` call, `await` on its coroutine frame, then the same
  loads through `container.` instead of `self.`.
- `stream.py` already imports from `collector.py` (`Collector`,
  `StreamingCollector`, `_CollectorSink`, `to_list`), so no new import edge or
  cycle is introduced by importing `counting`, `min_by`, `max_by`, `reducing`.
- `Stream.collect()` is a plain `def` returning the coroutine from
  `_drive_to()`, and runs `_check_not_consumed()` itself. `_drive_to()` runs it
  again; the check is a read, so calling it twice is harmless — `to_array()`
  already relies on that ("collect() runs `_check_not_consumed()` itself").

## Goals / Non-Goals

**Goals:**

- One implementation per algorithm: extremum, count, fold.
- Keep every existing test passing **unedited**. A test edit here is evidence
  of a behaviour change, not of a test that needed updating.
- Produce a defensible number for the per-element cost of the fold, recorded
  whichever way it lands, so this item is never re-proposed on vibes — the
  outcome `add-callsite-dispatch` reached.

**Non-Goals:**

- Touching `_ForEachSink`, `_MutableReductionSink`, `_FindSink`, `_MatchSink`.
  None has a collector counterpart, and the short-circuiting pair could not use
  one anyway: `Collector` has no way to express `cancellation_requested()`.
- Adding a `Collector` → short-circuit capability to make that possible.
- Making `_CollectorSink` faster in general. If the box indirection is the
  problem, the answer here is the fallback, not a `_CollectorSink` redesign —
  that would be its own change with its own benchmark.
- Any change to `collector.py`'s algorithms. The collector side is the
  survivor precisely because it is already the tested, documented one.
- Roadmap item 3's other parts. Only 3(c) is entangled with this change.

## Decisions

### Decision 1: The collector is the survivor, not the sink

The three algorithms could equally be unified by making `counting()` /
`min_by()` / `reducing()` delegate to the sinks. Rejected: a `Collector` is
the more general object — it must work when the caller supplies it to
`collect()`, and it must be reusable across concurrent collections, which is
why its state lives on a box. A sink cannot satisfy those constraints without
becoming a collector. Folding the general onto the special would mean the
collector factories keep their boxes *and* gain a sink dependency.

Direction also matters for the docs: README currently says `min_by` "Wraps
`Stream.min()`'s existing logic". After this change that sentence is backwards
and must be inverted, which is the README edit in the proposal's Impact.

### Decision 2: `Stream.reduce()` calls `reducing()` at its two arities, not a private core

`Stream.reduce()` normalizes its own overload first (`reduce(accumulator)` →
`identity = _UNSET`), and `reducing()` normalizes the same shape again from its
own three overloads. The temptation is to extract a private
`_reducing_core(identity, mapper, op)` that both call with already-normalized
arguments.

Rejected — measure the cost before paying for it: `reducing()`'s prologue is
three comparisons against `_UNSET` and two tuple unpacks, and it runs **once
per terminal call**, not once per element. `Stream.reduce()` maps onto the
public overloads directly:

```
reducing(accumulator)             # identity is _UNSET
reducing(identity, accumulator)   # identity given
```

One residual per-element cost is real and must be measured, not argued away:
`reducing`'s `_accumulate` tests `if mapper is not None` on every element, a
branch `_ReduceSink.accept()` does not have. It is a correctly-predicted branch
on a constant, so the expectation is that it disappears into noise — but it is
part of what the benchmark in Decision 3 is measuring, not an exemption from it.

### Decision 3: The gate is per terminal, measured on the terminal-dominated shape

The three terminals are independent code paths and are decided independently:
`count` regressing does not veto `min`/`max`.

**Harness** — the established one (Python 3.14.5, 20,000 elements, best of 5,
three independent process invocations per variant, interleaved reps in one
process), with one deliberate change: **no intermediate chain**. Prior
benchmarks in this repo used a chain of 8 `.map()` ops to isolate per-op cost;
here the terminal is the subject, so `Stream.of(*elements).count()` with an
empty chain is the shape that maximizes the terminal's share of per-element
cost. That is the worst case for this change, which is the case worth gating on.

**Variants per terminal:** baseline (as shipped) vs. collapsed
(`collect(...)`). For `min`/`max` and `reduce`, run both a sync and an async
user callable — the async path already pays a coroutine frame for the user
callable, so the collector frame is proportionally cheaper there, and the two
numbers may disagree.

**Threshold: +10% ns/element** on the sync variant of the terminal-dominated
shape, judged on the median of the three runs. Rationale for that number rather
than a tighter one: run-to-run spread on this harness has been ~10% in past
records (`add-callsite-dispatch`: 1907/1992/2162 for one variant), so a tighter
gate would not be distinguishable from noise; and `collapse-terminal-drive-loop`
already rejected a +10% variant, so +10% is the level this repo has treated as
real. A regression above the threshold on the sync variant sends that terminal
to the fallback even if its async variant is neutral.

**The figures are recorded whichever way they land** — in `design.md` and in
the roadmap **Done** entry — so a future reader does not re-litigate this.

#### Outcome, measured 2026-08-21

One refinement to the protocol on contact with the code: both forms are public
API on unmodified `HEAD` (`collect(counting())` already works), so baseline and
collapsed ran **interleaved in one process** against the same source rather
than as separate edit-and-remeasure invocations. That is strictly tighter — it
removes cross-process drift from the comparison the gate is judged on — and it
let every variant double as a correctness check, since both sides return a
value that can be compared directly.

| Variant | Baseline ns/element | Collapsed ns/element | Median delta |
|---|---|---|---|
| `count()` | 298 / 306 / 299 | 360 / 332 / 357 | **+19.6%** |
| `min(cmp)` sync | 467 / 442 / 422 | 608 / 560 / 522 | **+26.5%** |
| `min(cmp)` async | 558 / 551 / 513 | 648 / 626 / 651 | +16.2% |
| `reduce(acc)` sync | 332 / 356 / 354 | 622 / 562 / 601 | **+69.6%** |
| `reduce(0, acc)` sync | 369 / 331 / 355 | 630 / 590 / 601 | **+70.6%** |
| `reduce(acc)` async | 454 / 468 / 466 | 657 / 720 / 714 | +53.3% |

**All three terminals failed the +10% gate; all three took their Decision 4
fallback.** Every variant returned a result identical to its baseline, and the
full collapse passed all 505 tests with no test file edited, so this is purely
a cost finding.

`reduce` is worst by a wide margin for a reason worth recording: beyond the
box-and-coroutine cost the other two pay, `reducing()` routes every element
through `_classify_step`, a function call plus a tuple allocation and unpack
per element per callable — the exact per-element cost
`optimize-callable-dispatch` hoisted out and `add-callsite-dispatch` was
rejected for reintroducing.

The generalizable finding, which the `min`/`max` fallback then confirmed:
extracting a **sync** helper that *replaces* an existing per-element call is
free or better (`min` sync improved 442 -> 404 ns/element), while anything that
adds a coroutine frame or a box to the per-element path is not.

### Decision 4: The fallback is per terminal, and is "extract the core", not "do nothing"

If a terminal fails the gate, its sink stays and only the genuinely shared
logic moves to one place:

- **`min`/`max`** — extract the compare-and-keep step: given a comparator sign
  and `asc`, decide whether the new element displaces the held one, including
  `check_comparator_result_type(sign)` and the first-of-tied rule. That is a
  sync helper taking an already-awaited `int`, so it adds no coroutine frame
  and no box; it carries the contract comment, which is the part that has been
  duplicated verbatim. Both `_MinMaxSink.accept()` and `_extremum`'s
  `_accumulate` call it.
- **`count`** — no core worth extracting; `+= 1` is not shared logic. The
  honest fallback is to leave `_CountSink` alone and instead take roadmap item
  3(c) as originally written: drop its `Counter` box for a plain `int`, since
  the sink owns its container exclusively.
- **`reduce`** — the shared part is the `_UNSET`-seed rule and the
  empty-finishes-as-`None` rule, which are two lines and a comment, not an
  extractable function. The fallback is to leave `_ReduceSink` and record in
  both bodies that they implement one documented rule, with a pointer between
  them.

### Decision 5: `_UNSET` stays in `sink.py`

Both sides already import it from there, and its docstring already explains
why it lives in `sink.py` rather than `terminals.py` or `collector.py`. Nothing
in this change moves it, whichever terminals collapse.

## Risks / Trade-offs

- **[Per-element regression on the hottest terminals]** → The whole point of
  Decision 3. Gate before committing; per-terminal fallback in Decision 4.
- **[`reducing()`'s per-element `mapper is not None` branch is a real, if tiny,
  new cost on `Stream.reduce()`]** → Included in the measured variant rather
  than argued away. If `reduce` fails the gate on this alone, Decision 4's
  reduce fallback applies.
- **[Silent semantic drift between the two implementations that the tests do
  not cover]** → The two bodies are being merged, so any behaviour difference
  between them surfaces as a test failure on one side or the other. The audit
  before deleting each sink is: diff the sink's `accept`/`_finish` against the
  factory's `_accumulate`/`_finish` and confirm the only differences are where
  the dispatch state lives. Known candidate deltas to check explicitly:
  `_ReduceSink` classifies via `AsyncDispatch` while `reducing` uses
  `_classify_step` on the box — same shape, different spelling.
- **[Coverage falls below the 98% gate]** → Deleting three well-covered sinks
  removes covered lines, so the ratio can move either way. Run
  `uv run pytest --cov-fail-under=98` explicitly rather than assuming, and
  check whether any `reducing()` branch (the three-arity prologue, the
  `mapper is not None` path) becomes reachable only from tests that were
  previously exercising it from one direction.
- **[`ty` narrowing on `collect()`'s overloads]** → `count()` returns `int` and
  `min()`/`max()` return `T | None`; those come back through `collect`'s
  `Collector[T, Any, R]` overload as `R`. If `ty` cannot infer `R` tightly
  enough, a `cast` at the call site is acceptable — but note it, do not add one
  reflexively.
- **[Scope creep into `_CollectorSink`]** → Explicitly a Non-Goal. If the
  benchmark suggests `_CollectorSink` itself is the bottleneck, record that
  finding and stop; it is a separate change.

## Migration Plan

Internal refactor, no migration. Rollback is `git revert` of a single commit;
no persisted state, no public signature, no README parity checkmark changes.
The three terminals land as three separable commits so a single one can be
reverted if a regression shows up after merge.

## Open Questions

- Whether `Counter` still has a user after this change. If `count` collapses,
  `counting()` is the only remaining constructor of it; `Box` stays regardless.
  Safely deferrable: it changes nothing about the approach or the tasks, and is
  a one-line observation to make while doing task 5.
