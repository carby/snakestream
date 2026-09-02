## Why

`Stream.collect(supplier, accumulator, combiner)` and
`Collector(supplier, accumulator, combiner)` are the same four things in the
same order, driven by two sinks whose only per-element method is the same
source text:

| | `_MutableReductionSink` (`terminals.py:122-141`) | `_CollectorSink` (`collector.py:126-152`) |
|---|---|---|
| bases | `AsyncDispatch, TerminalSink[T]` | `AsyncDispatch, TerminalSink[T]` |
| dispatch | `_init_dispatch(accumulator)` | `_init_dispatch(collector.accumulator)` |
| `accept()` | `self._fn(self._container, element)` + the canonical shape | **byte-identical** |
| `_create_container()` | the caller's already-awaited container | `collector.supplier()` |
| `_finish()` | inherited identity | `container` when `finisher is None` |

Two specs already assert the identity in prose, which is a constructor call
written as a comment:

- `collector-protocol` line 20 — the accumulator's return value "SHALL be
  ignored, matching Java's `BiConsumer<A,T>` and the already-shipped
  `Stream.collect(supplier, accumulator, combiner)` form".
- `collector-protocol` line 156 — the combiner is retained and never invoked,
  "matching the posture `Stream.collect(supplier, accumulator, combiner)` and
  `reduce`'s combiner already have".

Java states it as a construction: `Collector.of(supplier, accumulator,
combiner)` exists precisely so the three-argument `collect` overload has a
`Collector` to be equivalent to.

**Now is the moment because the blocker was measured and is absent here.**
`collapse-terminal-collector-duplication` (2026-08-21, roadmap **Done**) tried
to route `count()`, `min()`/`max()` and `reduce()` through `_CollectorSink` and
reverted all three on its +10% gate (+19.6% / +26.5% / +69.6%, that change's
design.md Decision 3). It listed `_MutableReductionSink` under Non-Goals with
the reason *"None has a collector counterpart"* — true of `_ForEachSink` (no
container) and of `_FindSink`/`_MatchSink` (short-circuiting, which `Collector`
cannot express), and **false of this one**. Its counterpart is `Collector`
itself. The cost that failed the gate was the *box*: `counting()`/`reducing()`/
`min_by()` keep dispatch state on a supplier-made box and wrap the user's
callable in their own `async def _accumulate`, adding a coroutine frame and an
attribute hop per element. The three-argument form has neither — the user's
`accumulator` already *is* a `Collector`'s accumulator, `(container, element)`,
classified by the same `AsyncDispatch` triple on the same sink class. Measured
neutral; figures in design.md Decision 2.

## What Changes

- Build a `Collector(supplier, accumulator, combiner)` in `Stream.collect()`'s
  three-argument branch and drive it through the existing single-argument
  `Collector` path, so both forms reach one sink.
- Delete `_MutableReductionSink` from `terminals.py`, dropping its `BiConsumer`
  import if nothing else there uses it.
- Delete `Stream._collect_mutable()`, including its explicit
  `await _maybe_await(supplier)` — `TerminalSink.begin()` already routes
  `_create_container()` through `_maybe_await`, which is the contract that
  method's docstring states. Drop `stream.py`'s now-unused `_maybe_await`
  import.
- **Benchmark-gated**, on the harness and threshold
  `collapse-terminal-collector-duplication` established: Python 3.14.5, 20,000
  elements, interleaved round-robin, +10% ns/element on the sync variant sends
  this back. Figures recorded whichever way they land.
- No behaviour change, no public API change, no new or changed requirement. The
  existing suite passing **with no test edited** is the acceptance gate, as in
  `collapse-terminal-drive-loop`, `collapse-terminal-collector-duplication` and
  `extract-racing-task-lifecycle`.

## Capabilities

### New Capabilities

None. Behaviour-preserving internal refactor; `.openspec.yaml` sets
`skip_specs: true`, the same treatment as `extract-racing-task-lifecycle`,
`collapse-terminal-drive-loop` and `split-ops-into-ops-module`.

### Modified Capabilities

None. Three existing specs describe the behaviour involved and every
requirement must hold unchanged, which is precisely the acceptance criterion:

- `mutable-reduction-collect` — every clause survives verbatim. `supplier`
  called with no arguments exactly once (`begin()` runs once per composition
  under both executors, before the first pull); `accumulator` once per element
  as `accumulator(container, element)`; the container returned once the source
  is exhausted; both parts sync or async; `combiner` accepted and never
  invoked, sequential and parallel.
- `collector-protocol` — gains a second caller for the shape it already
  describes, not a new rule. Its two prose cross-references to the
  three-argument form (lines 20 and 156) become statements about one mechanism
  rather than about two that happen to agree.
- `terminal-sinks` — requires the three-argument `collect()` be executed by
  constructing a terminal sink, linking the chain onto it and returning its
  finished result. `_CollectorSink` **is** a terminal sink, so the requirement
  holds verbatim; only which sink class is constructed changes. Its
  "non-short-circuiting terminals never request cancellation" scenario also
  continues to hold — neither sink overrides `cancellation_requested()`.

## Impact

- `src/snakestream/stream.py` — `collect()`'s three-argument branch;
  `_collect_mutable()` deleted; `_maybe_await` import dropped.
- `src/snakestream/terminals.py` — `_MutableReductionSink` deleted;
  `BiConsumer` import dropped.
- `src/snakestream/collector.py` — unchanged. `_CollectorSink` is the survivor
  precisely because it is already the general, tested one.
- No import edge added: `stream.py` already imports `Collector` and
  `_CollectorSink` from `collector.py`.
- `tests/` — no edit. Nothing imports either deleted name; the only test whose
  name mentions the path,
  `test_callable_dispatch.py::test_collect_mutable_sync_call_returning_coroutine`,
  exercises the public three-argument `collect()`.
- README — no edit. No signature, return type, parity checkmark or migration
  entry: nothing a caller can observe changes, and that absence is a claim.
- `roadmap.md` — **Done** entry carrying the benchmark table.
