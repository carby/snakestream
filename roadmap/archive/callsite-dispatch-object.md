+++
id = "callsite-dispatch-object"
title = "Investigated and rejected: a `CallSite` object for `callable_dispatch.py`'s dispatch pattern"
filed = 2026-08-18
closed = 2026-08-18
outcome = "declined"
+++

**Investigated and rejected** replacing `callable_dispatch.py`'s hand-copied
async-dispatch pattern with a `CallSite` object. The pattern is genuinely
duplicated — `callable_dispatch.py` documents a 6-line shape as a 40-line
comment and 24 per-element sites across `stream.py`, `collector.py` and
`sort.py` retype it by hand, with `_classify_step` existing only to relieve
mccabe pressure in `to_map`/`reducing` and `sort.py` carrying the same state
as a positionally-indexed `state = [is_async, checked]` list. The proposal
was to wrap each callable in a small object owning that state.

Killed on measurement, at the benchmark gate the change's own tasks placed
after converting a single site. Harness matched the one
`optimize-callable-dispatch` and `redesign-pipeline-sink-chain` used (Python
3.14.5, 20,000 elements, chain of 8 `.map()` ops, best of 5, three runs per
variant); only `_MapSink` was converted, so with 8 `.map()` ops the figures
isolate per-site, per-element cost:

| Variant | ns/element | vs baseline |
|---|---|---|
| Baseline (inline shape, as shipped) | 1907, 1992, 2162 | — |
| Floor (dispatch logic deleted; sync-only, incorrect) | 1826, 1878, 1998 | ~0% |
| `CallSite.call()` sync, caller branches on `.is_async` | 2529, 2589, 2840 | **+32%** |
| `CallSite` with `async def __call__` | 3399, 3444, 3468 | **+75%** |

The decisive figure is the floor: deleting the dispatch logic outright buys
nothing measurable over the baseline, so the inline five-branch shape costs
approximately zero — two attribute loads and two branches the CPU predicts
correctly after the first element, with no Python-level call and no
allocation. The comparison is therefore not "abstraction vs. cheaper
abstraction" but "abstraction vs. free", and both variants pay a
Python-level call per element per site that the inline code does not (~180
ns/site/element for the coroutine frame, ~70 ns for the bound-method call
alone). The design's stated fallback — a two-shape `CallSite` picking a sync
fast path in `__init__` — does not help, since the fast path still has to be
reached through the call that is itself the cost. `optimize-callable-dispatch`
bought 2.6x by hoisting exactly these branches out of the per-element path;
the two variants give back roughly half and roughly a fifth of that.

**Consequence:** the duplication is now a deliberately-accepted cost with
numbers behind it rather than an open cleanup item, and should not be
re-proposed without new evidence. Anyone adding a 25th dispatch site should
still copy the canonical-shape comment in `callable_dispatch.py` — that
comment is load-bearing, not a smell to be refactored away. No code changed;
the working tree was reverted to HEAD and the full suite (394 tests) passes
unmodified. See
`openspec/changes/archive/2026-08-18-add-callsite-dispatch` for the proposal,
design, and `benchmark-findings.md`.

**One residual finding was salvaged and acted on.** The investigation
established that per-callable classification independence — `to_map`'s
key/value/merge functions and `reducing`'s mapper/binary operator each
classifying on their own, so any mixture of sync and async among them works
— was real behavior with **no test coverage**: `tests/test_to_map.py` and
`tests/test_reducing.py` each covered all-sync and all-async but never a
mixed pair. Closed by adding the five mixed-mode tests (sync key + async
value, async key + sync value, sync mappers + async merge on a colliding
key, sync mapper + async operator, async mapper + sync operator) and
promoting the rejected change's drafted delta into the `callable-dispatch`
spec as a new **Classification state is per callable** requirement. All five
passed on first run — the behavior was already correct, so this is coverage
and documentation of existing behavior, not a fix. Written directly to
`openspec/specs/callable-dispatch/spec.md` rather than through a change of
its own, since the requirement text already existed in the rejected
change and would otherwise have been archived away unapplied.
