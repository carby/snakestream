+++
id = "collapse-mutable-reduction-onto-collector"
title = "Three-argument `collect()` runs on the collector sink (`collapse-mutable-reduction-onto-collector`)"
filed = 2026-09-02
closed = 2026-09-02
outcome = "shipped"
shipped_as = "collapse-mutable-reduction-onto-collector"
+++

**`collapse-mutable-reduction-onto-collector`** (2026-09-02) —
`_MutableReductionSink` (`terminals.py`) and `_CollectorSink`
(`collector.py`) were the same bases, the same `AsyncDispatch` triple and a
byte-identical `accept()`, differing only in where the container came from.
`collect()`'s three-argument branch now builds a
`Collector(supplier, accumulator, combiner)` and drives it through the
existing `_CollectorSink` path the single-argument branch already used;
`_MutableReductionSink` and `Stream._collect_mutable()` are deleted, along
with `terminals.py`'s now-unused `BiConsumer` import and `stream.py`'s
now-unused `_maybe_await` import (`TerminalSink.begin()` already routes
`_create_container()` through `_maybe_await`, so the supplier needs no
separate awaiting once it lives on a `Collector`). `ty check` stayed clean
without the `cast` design.md Decision 5 anticipated needing between
`collect()`'s `BiConsumer[R,R]` combiner and `Collector.__init__`'s
`Combiner[A] | None` — the mismatch `ty` was expected to reject did not
materialize, so none was added, per the task's own "do not add the cast
preemptively."

**What makes this different from `collapse-terminal-collector-duplication`
(2026-08-21, below), which rejected the same *shape* of collapse for
`count()`, `min()`/`max()` and `reduce()`:** that change's three sinks have
no `Collector` counterpart to fold onto — `counting()`/`min_by()`/
`reducing()` keep their own per-collection dispatch state on a
supplier-made box and wrap the user's callable in their own
`async def _accumulate`, so routing through them adds a coroutine frame and
an attribute hop per element that the dedicated sinks don't pay. The
three-argument `collect()` form has neither box nor wrapper: its
`accumulator` already *is* a `Collector`'s accumulator, `(container,
element)`, dispatched by the same `AsyncDispatch` attributes on the same
sink shape `_MutableReductionSink.accept()` ran. Counterpart versus no
counterpart, box versus no box — that is the distinction, not the
conclusion "collector-routing terminals is now safe to retry." Anyone
reading this as licence to re-open `_CountSink`, `_ReduceSink` or
`_MinMaxSink` is reading it backwards; those remain a measured, deliberately
rejected trade.

**Measured against the `collapse-terminal-collector-duplication` gate**
(+10% ns/element on the sync variant, Python 3.14.5, 20,000 elements,
interleaved round-robin, best of 3 across 10 rounds), pre-change baseline
(`_MutableReductionSink` via the public three-argument `collect()`, recorded
before any code changed) against the shipped code (the same three-argument
`collect()` call, now routed through `_CollectorSink`), ns/element:

| variant | baseline | shipped | delta |
|---|---|---|---|
| sync accumulator | 321.2 / 327.9 / 341.9 | 299.2 / 320.4 / 325.8 | −6.9% / −2.3% / −4.7% |
| async accumulator | 390.8 / 427.9 / 401.6 | 417.9 / 409.9 / 433.0 | +6.9% / −4.2% / +7.8% |

Every sync delta negative and every figure inside the ~10% run-to-run noise
this harness has shown before; the gate is judged on the sync median
(−2.3%), well under +10%, so the change **shipped rather than reverted** —
the branch design.md's Decision 4 risk did not take.

988 tests green, unchanged from before — `git diff --stat tests/` empty, no
test file, name or import touched (the only test naming the deleted path,
`test_callable_dispatch.py::test_collect_mutable_sync_call_returning_coroutine`,
exercises the public three-argument `collect()` and passed unedited).
Coverage 98.62%; `terminals.py` shrank from 129 to 113 statements, 0 missed
before and after, 100% both times — the sink it lost was fully covered, not
under-tested. No README migration entry, and that absence is a claim: no
signature, return type, parity checkmark or observable behaviour changed.
`skip_specs: true`.
