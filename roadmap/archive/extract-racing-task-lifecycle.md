+++
id = "extract-racing-task-lifecycle"
title = "The racing `FIRST_COMPLETED` merge is written once (`extract-racing-task-lifecycle`)"
filed = 2026-09-02
closed = 2026-09-02
outcome = "shipped"
shipped_as = "extract-racing-task-lifecycle"
+++

**`extract-racing-task-lifecycle`** (2026-09-02) — the `FIRST_COMPLETED`
merge over N branches' `anext()` existed twice, verbatim, in
`race_through()` and `_release_in_order()`, and the module docstring's
"four primitives do the work" did not name it because it had been copied
rather than extracted. Both docstrings already admitted it in prose —
*"the same `FIRST_COMPLETED` merge `race_through()` runs, with a buffer in
front of the yield"* and *"same clean-up as `race_through()`'s, plus closing
the branches"* — which is a function signature written as a comment.

**What shipped is the smaller of two extractions, and the choice was
measured.** `_racing_branches()` is an `@asynccontextmanager` beside
`_maybe_aclosing()` owning the arming and the teardown — twelve of the twenty
duplicated lines. The eight-line `while`/`for` body stays in both callers,
because that is the half that genuinely differs: one yields a completed
result as it stands, the other buffers it by source index.

**Rejected: extracting the whole merge as a `merge()` async generator.** It
removes all twenty lines and costs one async-generator hop per element on the
racing path. Python 3.14.5, 20,000 elements, `map(x + 1)`, 4 workers, all
variants draining into the same `_CountSink`, ten interleaved samples,
µs/element:

| variant | order-blind, min / median | ordered delivery, min / median |
|---|---|---|
| baseline | 7.12 / 7.40 | 9.42 / 9.62 |
| `merge()` generator | 7.25 / 7.70 — **+2.0% / +4.1%** | 9.79 / 10.05 — **+3.9% / +4.5%** |
| `@asynccontextmanager` | 7.07 / 7.47 — −0.7% / +0.9% | 9.41 / 9.55 — −0.1% / −0.7% |

~4%, consistent across both pipeline shapes and both statistics, appearing
identically whether the merge feeds a yield or a reorder buffer — which is
what a per-element charge looks like and what a per-composition one does not.
About a fifth of the reordering half of the barrier again (0.68 µs/element,
per `race_through()`'s docstring), so not lost in the machinery's own noise.
Same family of finding as `add-callsite-dispatch` and as
`Sequential.value()`'s existence: **a generator hop on a per-element path is
never free here, and the comparison is abstraction against free rather than
abstraction against cheaper abstraction.** Do not re-propose without new
evidence.

**Two traps in measuring this path, both of which produced a wrong answer
first.** Block-sequential timings drift by more than the effect: a first pass
reported the `@asynccontextmanager` variant at +3.3%, which is impossible for
an extraction that runs once per composition, and interleaving round-robin
dissolved it. And when the verification benchmark loaded the pre-change module
alongside the shipped one to interleave them, it fed the shipped
`OrderDemand.IF_ORDERED` to *both* — `_split_point()` compares with `is`, the
copied module defines its own enum, so the pre-change side silently took the
no-split path and read as 34% *faster* until its ordered figure was noticed
matching its own order-blind one. Anyone re-measuring across two copies of
`execution.py` must give each its own enum members.

**The one behaviour settled rather than preserved: both merges now close
their branches.** The barrier did and the plain merge did not, on a reason
that names the window — a branch parked on a full window has a finally of its
own to run and no outstanding `anext()` for a cancel to reach. That does not
extend to the unwindowed path, but nothing established the converse either,
and `aclose()` on an exhausted generator is a no-op so unifying cannot
double-close. **No spec changed**: `racing-encounter-order` already required
the shared source be closed exactly as it is without a barrier, with two
equal-close-count scenarios; this makes one mechanism true where two
previously happened to agree, and those scenarios were the regression gate.

988 tests green, unchanged from before — `git diff --stat tests/` empty, no
test file, name or import touched. Coverage 98.64%; `execution.py` lost one
statement and two branch arcs (three `for` loops across two `finally` blocks
became two in one), missed statements 0 before and after, and its two partial
branches are the same pre-existing site shifted by the added helper. No
README migration entry, and that absence is a claim: nothing a caller can
observe changed. `skip_specs: true`.
