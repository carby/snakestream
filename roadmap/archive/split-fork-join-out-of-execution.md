+++
id = "split-fork-join-out-of-execution"
title = "`execution.py` splits into `pipeline.py`, `fork_join.py`, `execution.py`"
filed = 2026-09-10
closed = 2026-09-10
outcome = "shipped"
shipped_as = "split-fork-join-out-of-execution"
+++

**`execution.py` splits into `pipeline.py`, `fork_join.py`, `execution.py`**
(closed 2026-09-10; not filed as a roadmap item — found by exploration on
2026-09-10 against an empty Now and Next queue). Shipped as
`split-fork-join-out-of-execution`.

`execution.py` had grown to 600 lines and 15 top-level definitions, 11 of
them — 332 lines, 55% of the file — one concern's private machinery:
fork/join batch dispatch. `stream.py`, the module's only consumer, touched
exactly three names from all of it: `Executor`, `SEQUENTIAL`, `FORK_JOIN`.
The split follows the house pattern already shipped for `collectors.py`
out of `collector.py`, `comparator.py` out of `sort.py`, `ordering.py` out
of `sink.py`/`execution.py`, and `unseeded.py` out of `sink.py`.

The one real obstacle was a dependency cycle: `_ForkJoin.elements()` needs
the fork/join dispatch, which needs the single-ordered-pass primitive
(`stream_through`) that `_Sequential.elements()` also needs. A naive
two-way split walks straight into `execution.py` and `fork_join.py`
importing each other. The fix was a third module rather than a deferred
import or an injected parameter: `pipeline.py` (Java's `AbstractPipeline`,
literally — `wrap_sink()`/`_copy_into()` plus the three drive shapes)
sits *below* both `fork_join.py` and `execution.py`. The resulting shape is
a triangle, not a clean stack — `execution.py` imports `stream_through`,
`feed_through` and `drain` from `pipeline.py` directly, not only by way of
`fork_join.py` — and a design.md correction made during review records why
that triangle is forced rather than an oversight: any acyclic arrangement
of a sequential implementation, a parallel implementation, and a protocol
that picks between them has this shape, because `stream_through()` sits on
both upward edges for an algorithmic reason (fork/join's order barrier
degenerates to a single sequential pass, so fork/join *contains* sequential
execution as a sub-case) rather than as a reach into a shared utility bag.
The general rule the review converged on, worth carrying into the next
module split: a name lives at or below its lowest consumer. It settles
every placement question this change raised — `wrap_sink`/`maybe_aclosing`
at/below `pipeline.py` (two consumers each), `_copy_into` inside
`pipeline.py` (one consumer), `_accumulate_into` inside `fork_join.py` (one
consumer, see below), `stream_through` at/below `fork_join.py` — and it is
why moving `wrap_sink`/`maybe_aclosing` up into `execution.py` was never a
live option: it would invert the chain and produce two import cycles, not
one. `execution.py` is the only module left naming both `pipeline.py` and
`fork_join.py`, which is exactly what an executor value is for.

Five duplications collapsed once the fork/join half was visible together
in its own file rather than spread across 330 lines of a much larger one:
`_gather_or_cancel(tasks)` (the cancel-siblings-and-drain idiom, written
verbatim three times and over `in_flight` a fourth), `_rounds(source,
workers)` (the round loop — seed, pull, yield, stop-on-short-round, ramp —
written twice, with the ramp's long comment pointed at from three sites),
and `_shared_state(chain)` (the state-map build, written twice). All three
run once per round or once per composition, never once per element, so
none of them touches the measured decisions this change deliberately left
alone (`ramp-batch-growth-geometrically`'s factor of 8, `WORKERS = 4`,
`_Sequential.value()`'s fused-push override). `_run_round`/
`_run_partition_round` were measured as a sixth candidate and declined:
once decision 3 landed each was a two-line function differing only in
*which* worker runs and *what* comes back, and a `runner` parameter would
have erased two clear names and two clear return types to save two lines.

Renames were mechanical, not chosen: CLAUDE.md's naming rule ("underscored
iff no other module uses it") drops the underscore on any name a module
boundary now crosses. `wrap_sink`, `stream_through`, `feed_through`,
`drain`, `maybe_aclosing`, `fork_join_through` and `fork_join_partitioned`
went bare; `WORKERS` moved module (from `execution.py` to `fork_join.py`)
but stays bare, since `execution.py` still imports it to bind
`FORK_JOIN = _ForkJoin(WORKERS)`, and `from snakestream.execution import
WORKERS` still resolves through that import — so the existing
`name-by-visibility-not-underscore` Migration entry naming that path
stays true without a new one.

Two `openspec/specs/**/spec.md` statements (four SHALL/Purpose sentences
across `pipeline-composition` and `stream-iterator`) named `_wrap_sink()`
by its pre-rename spelling. `skip_specs: true` was chosen over a delta:
no requirement's substance changed, only the spelling and home of an
internal helper it happens to name, so a delta would have produced a
MODIFIED-Requirements block restating four requirements verbatim but for
one token — the same "specs describe behaviour, not spelling" principle
`extract-unseeded-fold-module` set. The four sentences were corrected in
place, scoped to exactly the identifier plus the module name where a
sentence already named a location; no SHALL was added, removed, reordered
or reworded.

A peer-session review before archiving caught two more items past the
change's own scope:
- `pipeline.py`'s `copy_into` was left bare after the move despite having
  no cross-module caller (only comment mentions, which don't count under
  the naming rule) — a regression against the rule the change itself
  invokes, uncatchable by `test_name_visibility.py` because that test only
  enforces the "no cross-module private import" half of the rule, not "a
  bare name really has no caller." Renamed back to `_copy_into()`.
- `accumulate_into` was rule-compliant as a bare `pipeline.py` name (used
  from `fork_join.py`) but had exactly one consumer and fork/join-specific
  semantics, and its own docstring had to name its single caller by module
  to explain itself — the same shape decision 6 already used to justify
  putting the state-map build in `fork_join.py` rather than `pipeline.py`.
  Moved next to its only caller, `_run_partition_sync`, as
  `_accumulate_into`. This narrows the change's original design — its
  decision-1 diagram had listed `accumulate_into` as one of seven
  `pipeline.py` primitives; `pipeline.py` now exports six.

Confirmed by benchmark, not gated on one, per the change's own claim that
nothing here sits on a per-element path: `Stream(vals).parallel().map(
cpu_bound).collect(to_list())` vs `.sequential()`, 4000-iteration
CPU-bound mapper, median of 5 trials, n=200 and n=4096, run against the
working tree and against pre-split `execution.py` (via `git stash` of
just this change's files) on both `3.14` and `3.14t`. Figures agreed
within trial-to-trial noise on both legs (e.g. 3.14t, n=4096: before
seq=580.75ms/par=312.34ms, after seq=581.12ms/par=319.91ms) — no
measurable change, as expected for a pure module move.

No roadmap item is closed by this change — none existed for it — so
`roadmap/README.md`'s Now/Next/Later index is unaffected.
