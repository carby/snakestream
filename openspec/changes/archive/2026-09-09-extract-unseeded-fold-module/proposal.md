## Why

`UNSET`, `unseeded()`, and `UnseededSink` currently live in `sink.py`, whose own
module docstring advertises exactly four sink shapes (`IntermediateSink`,
`StatefulSink`, `TerminalSink`, `GeneratorBridgeSink`) — a sink-protocol module.
But `unseeded()` reaches two implementations of the same fold rule: the
sink-shaped one (`UnseededSink`, used by `terminals.py`) and two dataclass boxes
in `collectors.py` (`_ExtremumBox`, `_ReduceBox`) that are deliberately *not*
sinks (design Decision 3 of `collapse-unseeded-accumulation-rule`). `sink.py`
can't honestly claim to own a concept half of whose implementations live
outside the sink protocol — and its docstring doesn't try to: it is silent
about the trio entirely, so the module has been carrying a third thing it
never accounts for. Inlining the rule rather than centralizing it was rejected
in that same decision — before it, the rule stood at five sites (three
`TerminalSink` subclasses and two collector closures), and `unseeded()` is the
only mechanism reaching both halves, since a base class cannot reach a closure.
It is called from three places today, two of them the non-sink boxes; inlining
it again would restate one check across two modules with no shared type to keep
them in sync. The fix is to give the shared *rule* its own home instead of
stretching `sink.py`'s, and to put each of its two applications with the
module that consumes it.

Filed as `roadmap/items/sink-sentinel-placement.md`, gated on exactly this
question; resolved by exploration on 2026-09-09.

## What Changes

- Add a new leaf module, `unseeded.py`, holding the shared fold vocabulary and
  only that: `UNSET` and `unseeded()`. It imports nothing from the package.
- Move `UnseededSink` into `terminals.py` — its only consumer — as
  `_UnseededSink`. All three of its subclasses (`ReduceSink`, `MinMaxSink`,
  `FindSink`) already live there, and `terminals.py` already imports
  `TerminalSink`, so this adds no import edge and removes `unseeded.py`'s only
  two. Per CLAUDE.md's naming rule, a name no other module uses is
  underscored.
- Remove those three from `sink.py`. Its module docstring needs no edit — it
  already describes only the sink protocol and its four shapes, so the move
  makes it accurate by subtraction of code rather than by rewriting prose. It
  gains no pointer to the new module either, since `sink.py` will not reference
  it (unlike `ordering.py`, which it imports from, which is why *that* pointer
  exists).
- Update the three importers (`stream.py`, `terminals.py`, `collectors.py`) to
  import `UNSET`/`unseeded()` from `unseeded.py` instead of `sink.py`.
- **BREAKING**: none — all three names are internal (no re-export from
  `snakestream/__init__.py`), so this is invisible to callers per the [Naming]
  rule in `CLAUDE.md`.

## Capabilities

### New Capabilities

None — this changes module placement, not observable behavior.

### Modified Capabilities

None — no spec in `openspec/specs/` names `UNSET`, `unseeded()`, or
`UnseededSink`; this is a zero-delta refactor (`skip_specs: true` set in
`.openspec.yaml`).

## Impact

- `src/snakestream/sink.py` — loses `UNSET`, `unseeded()`, `UnseededSink` and
  their docstrings. Module docstring unchanged.
- `src/snakestream/unseeded.py` — new; holds `UNSET` and `unseeded()`, and
  imports nothing from the package. (Name rationale in `design.md`.)
- `src/snakestream/terminals.py` — gains `_UnseededSink` and the underscore on
  it; its three subclasses' base changes name. No new import edge.
- `src/snakestream/stream.py`, `src/snakestream/collectors.py` — import line
  changes only; no call-site behavior changes.
- `tests/` — **no changes**. Checked: no test imports `UNSET`, `unseeded` or
  `UnseededSink`. `test_name_visibility.py:45` writes
  `from snakestream.sink import _UNSET` as a *synthetic fixture string* naming
  a private symbol that does not exist, to exercise the checker itself — it is
  not a real import and the move does not touch it. The other hits
  (`test_collector_combiners.py`, `test_terminal_sinks.py`) are comments and a
  test name. No new visibility violation either: `UNSET`/`unseeded()` stay bare
  and cross-module, and `UnseededSink` becomes `_UnseededSink` exactly because
  it stops crossing a boundary.
- `roadmap/items/sink-sentinel-placement.md` — closed by this change (task
  5.1): its prose moves to `roadmap/decisions.md` and the index is
  regenerated, per the roadmap's own closing rule now that the work ships
  here.
