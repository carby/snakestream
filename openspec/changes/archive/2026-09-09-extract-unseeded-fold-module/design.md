## Context

`sink.py` currently defines `UNSET`, `unseeded()`, and `UnseededSink` alongside
the sink protocol itself (`Sink`, `Op`, `IntermediateSink`, `StatefulSink`,
`TerminalSink`, `GeneratorBridgeSink`). The three do not have equal claims on a
new home, and counting importers is what separates them: `UNSET` has three
(`stream.py`, `terminals.py`, `collectors.py`), `unseeded()` two
(`terminals.py`, `collectors.py`), and `UnseededSink` exactly one
(`terminals.py`, where all three of its subclasses are also defined). See
proposal.md - Why for the motivation.

## Goals / Non-Goals

**Goals:**
- Name the new module, and settle which of the three names belong in it.
- Leave `unseeded.py` with no package imports at all, and add no import edge
  anywhere else.

**Non-Goals:**
- No change to the `Sink`/`Op` protocol, `unseeded()`'s rule, or any call-site
  behavior.
- No test changes. Verified: no test imports the trio, so despite this being a
  module move, nothing under `tests/` needs an import update — see
  proposal.md - Impact for why `test_name_visibility.py:45`'s
  `from snakestream.sink import _UNSET` is not a counter-example.
- No change to `collectors.py`'s `_ExtremumBox`/`_ReduceBox` — they keep using
  `UNSET`/`unseeded()` exactly as before, just from a different import path.

## Decisions

**Module name: `unseeded.py`.** It names the fold rule directly — the same
naming move `ordering.py` made for the encounter-order vocabulary (a module
named for the concept, not a container word). Considered and rejected:
- `fold.py` — reads as a general-purpose fold/reduce utility module, which
  overclaims; this module implements exactly one specific rule ("an
  accumulation that never saw an element finishes as `None`"), not a fold
  abstraction.
- `accumulation.py` — same overclaim in the other direction: every collector
  in `collectors.py` accumulates, and only two of its boxes are unseeded.
  `unseeded.py` scopes the module to the actual concept, matching its
  contents 1:1 (the sentinel and the rule that reads it).

**`unseeded.py` holds only `UNSET` and `unseeded()`; `UnseededSink` goes to
`terminals.py` as `_UnseededSink`.** The trio is not one unit. What belongs in
a shared module is what is actually shared, and the class is shared by nothing:

```
  before                              after

  unseeded.py --> sink.py             unseeded.py       (no package imports)
       |          (TerminalSink)       ^    ^    ^
       |          type.py (T)          |    |    |
       v                        terminals.py |  stream.py
  UNSET, unseeded(), UnseededSink   (_UnseededSink)
       ^      ^      ^                      collectors.py
       |      |      |                      |
  terminals  collectors  stream        terminals.py --> sink.py (unchanged)
```

`unseeded.py` currently imports `TerminalSink` and `T` for one reason: to
define a class with a single consumer. That consumer already imports
`TerminalSink` itself, so moving the class there **adds no import edge and
removes both of `unseeded.py`'s**, leaving it a true leaf. Nothing reverses in
either layout — `sink.py` has zero references to `unseeded.py`, checkable with
`grep -n unseeded src/snakestream/sink.py`.

Two further things fall out, and both are confirmations rather than costs:

- **The underscore returns for the right reason.** CLAUDE.md: a module-level
  name is underscored *iff* no other module uses it. `UnseededSink` was bare
  only because it crossed `sink.py` -> `terminals.py`; delete the crossing and
  it is `_UnseededSink` again — what `collapse-unseeded-accumulation-rule`
  called it before `name-by-visibility-not-underscore` bared it.
- **It removes an asymmetry the trio was hiding.** The rule has two
  implementations — `_UnseededSink` for sinks, `_ExtremumBox`/`_ReduceBox` for
  collectors — that deliberately share no base class (Decision 3 of
  `collapse-unseeded-accumulation-rule`). Keeping one beside the rule while the
  other sits in `collectors.py` privileges it for no reason. Now the shared
  vocabulary is central and each application sits with its consumer.

Rejected: keeping the trio together on the grounds that `UnseededSink` "*is*
the concept" (the roadmap item's positive argument). That argument was built to
rule `sink.py` **in** against a move; once the move is granted, it no longer
picks a destination, and the importer counts do.

**`sink.py`'s module docstring is not edited at all.** It describes the Op/Sink
pair, the push protocol, the four shapes it holds, and a pointer to
`ordering.py` — and never mentions `UNSET`, `unseeded()` or `UnseededSink`.
There is no fold-vocabulary paragraph to remove; the docstring becomes accurate
by subtraction of *code*, not by rewriting prose. That silence is itself the
evidence for the move: the module has been holding a third thing its own
docstring could not account for. Nor does it gain a pointer to `unseeded.py` —
the `ordering.py` pointer exists because `sink.py` imports from it, and after
this move `sink.py` will have no relationship to `unseeded.py` in either
direction. What does travel with the code is `UNSET`'s own standalone comment
(the stale "both need it and neither is downstream of the other" line that
started this roadmap item), which is rewritten in its new home to name the
actual importers.

**Importer updates are the only other touch.** `stream.py`, `terminals.py`,
`collectors.py` each currently import `UNSET` (and `terminals.py` also
`unseeded`, now that it defines `_UnseededSink` itself) from
`snakestream.sink`; each moves to `snakestream.unseeded`, alongside whatever
they still need from `sink.py` (`terminals.py` keeps its `TerminalSink` import
from `sink.py`; `stream.py` keeps `Op`, `TerminalSink`).
`stream.py:55` also carries a comment contrasting
its own `_MISSING` sentinel against "sink.py's UNSET" — that line updates to
name `unseeded.py` instead, or the move misdescribes where the thing it's
distinguishing itself from now lives.

## Risks / Trade-offs

[A 2-symbol module reads as thin] → Already weighed against the alternative
(inlining the rule at its call sites) and rejected on those terms, not on
module size — the concern that matters is a thin *function* forcing duplicate
checks on callers, which doesn't apply to a rule with no branch a caller could
want to control. Moving `_UnseededSink` out makes the module thinner still, and
that is the point: what remains is exactly what more than one module uses, with
no imports of its own. `ordering.py` is the accepted precedent for a module
scoped this narrowly.

[Coverage on the new module] → No new logic is introduced, so no new tests are
needed; existing tests exercising `ReduceSink`, `MinMaxSink`, `FindSink`,
`_extremum`, and `reducing`/`reduce()` already cover every line that moves.

## Migration Plan

1. Create `src/snakestream/unseeded.py`: move `UNSET` and `unseeded()` with
   their comment and docstring; no package imports.
2. Move `UnseededSink` into `terminals.py` as `_UnseededSink`, above its three
   subclasses, and repoint them at the new name.
3. Remove all three definitions from `sink.py`, leaving its module docstring
   untouched.
4. Update imports in `stream.py`, `terminals.py`, `collectors.py` to pull
   `UNSET`/`unseeded()` from `snakestream.unseeded`; fix the `stream.py:55`
   comment's module reference, and `unseeded()`'s own docstring, which says the
   rule reaches terminals "through `UnseededSink` below" — no longer below it.
5. Run `uv run ruff check .`, `uv run ruff format --check .`,
   `uv run ty check src`, and `uv run pytest --cov-fail-under=98` — a pure
   move should leave coverage and all three checks unchanged.

Rollback is a single revert; nothing outside `src/snakestream/` changes, and
no data or state migrates.
