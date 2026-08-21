## Why

Three algorithms are written twice in this library, once as a `TerminalSink` in
`terminals.py` and once as a `Collector` factory in `collector.py`:

| Terminal sink | Collector factory | Duplication |
|---|---|---|
| `_MinMaxSink` (`terminals.py:84-119`) | `_extremum` (`collector.py:326-355`) | Same `_UNSET`-seed / comparator-sign / first-of-tied algorithm, down to a verbatim copy of the comparator-contract comment |
| `_CountSink` (`terminals.py:20-27`) | `counting()` (`collector.py:139-146`) | Same `Counter` box, same `+= 1`, same `.value` finish |
| `_ReduceSink` (`terminals.py:53-81`) | `reducing()` (`collector.py:391-424`) two-arg form | Same `_UNSET`-seed fold, same "empty finishes as `None`" rule |

README already records the direction of that duplication as intentional
layering — `min_by` "Wraps `Stream.min()`'s existing logic", `reducing`
"Mirrors `Stream.reduce()`'s existing semantics" — but no code is actually
shared, so the comparator-contract fix, the first-of-tied tie-break and the
empty-source rule each have two homes that must be kept in step by hand.

Now is the moment because the blocker is gone: the `Collectors` framework is
complete as of 2026-08-20 (roadmap **Done**), so the factories these terminals
would fold onto are settled, and `redesign-collector-shape` made
`_CollectorSink` a real terminal sink — `collect(collector)` no longer goes
through the generator bridge, so folding a terminal onto a collector no longer
means moving it onto a slower drive.

## What Changes

- Route `Stream.count()`, `Stream.min()` / `Stream.max()` and `Stream.reduce()`
  through the existing collector factories — `collect(counting())`,
  `collect(min_by(c))` / `collect(max_by(c))`, `collect(reducing(...))` — so
  each algorithm has exactly one implementation.
- Delete `_CountSink`, `_MinMaxSink` and `_ReduceSink` from `terminals.py`.
  `_ForEachSink`, `_MutableReductionSink`, `_FindSink` and `_MatchSink` stay:
  they have no collector counterpart.
- Invert the layering note in README's `min_by` / `max_by` / `reducing` rows —
  the collector becomes the implementation and the `Stream` method the wrapper.
  No signature, return type or parity-table checkmark changes.
- **Benchmark-gated, per terminal.** Routing through `_CollectorSink` adds a
  Python-level coroutine call, a supplier-made box and one extra attribute hop
  per element on paths that are direct field access today — the same shape of
  trade that killed `add-callsite-dispatch` (roadmap **Done**), which measured
  ~180 ns/element for exactly that coroutine frame. The change is not committed
  until measured on the established harness (Python 3.14.5, 20,000 elements,
  best of 5, three independent runs per variant), with a stated regression
  threshold, and the figures are recorded whichever way they land.
- **Documented fallback if a terminal regresses past the threshold:** keep that
  sink and extract only its shared core — for `min`/`max` the comparator
  compare-and-keep step, which is where the contract comment and the tie-break
  rule actually live. A per-terminal decision: `count` regressing does not veto
  `min`/`max`.
- No behaviour change, no public API change, no new or changed requirement. The
  existing 505-test suite passing **with no test edited** is the acceptance
  gate, exactly as `collapse-terminal-drive-loop` used it.

## Capabilities

### New Capabilities

None. This is a behaviour-preserving internal refactor, so the change sets
`skip_specs: true` in its `.openspec.yaml` — the same treatment as
`collapse-terminal-drive-loop`, `collapse-collector-sink-duplication` and
`split-ops-into-ops-module`.

### Modified Capabilities

None. Four existing specs describe the behaviour involved and every one of
their requirements must hold unchanged, which is precisely the acceptance
criterion:

- `terminal-sinks` — requires `count()`, `min()`, `max()` and `reduce()` to be
  executed by constructing a terminal sink, linking the chain onto it and
  returning its finished result. `_CollectorSink` **is** a terminal sink, so
  the requirement holds verbatim; only which sink class is constructed changes.
  Its "non-short-circuiting terminals never request cancellation" scenario also
  continues to hold — `_CollectorSink` does not override
  `cancellation_requested()`.
- `collector-min-max`, `collector-reducing`,
  `collector-counting-summing-averaging` — the collector-side contracts these
  terminals fold onto. Unchanged; they gain a second caller, not a new rule.
- `comparator-contract` — `check_comparator_result_type` is called on the sign
  in both copies today and in the single survivor afterwards.

## Impact

- `src/snakestream/terminals.py` — three sink classes deleted (~60 lines); the
  `Counter`, `Comparator`, `Accumulator` and `check_comparator_result_type`
  imports go with them.
- `src/snakestream/stream.py` — `count()`, `_min_max()` and `reduce()` become
  `collect(...)` calls; imports of the three deleted sinks drop.
- `src/snakestream/collector.py` — no algorithm change expected. `reducing()`'s
  argument-shuffling prologue is the one open question the design must settle,
  since `Stream.reduce()` reaches it with an already-normalized
  `(identity, accumulator)` pair and must not pay for re-deriving it per call.
- `tests/` — no test should need editing. `tests/test_count.py`,
  `test_min_max.py`, `test_reduce.py` and the parallel-stream terminal tests are
  the regression gate.
- `README.md` — wording only, in the `min_by` / `max_by` / `reducing` rows.
- `roadmap.md` — item 1 moves from **Now** to **Done**, carrying the benchmark
  figures and, if the fallback is taken, which terminals kept their sinks and
  why. Item 3(c) (`_CountSink`'s `Counter` box) is resolved by this change if
  `count` collapses, and must be struck from that batch either way.
