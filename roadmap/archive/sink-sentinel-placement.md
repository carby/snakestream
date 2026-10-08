+++
id = "sink-sentinel-placement"
title = "`UNSET`, `unseeded()` and `UnseededSink` move out of `sink.py`"
filed = 2026-09-03
closed = 2026-09-09
outcome = "shipped"
shipped_as = "extract-unseeded-fold-module"
+++

**`UNSET`, `unseeded()` and `UnseededSink` move out of `sink.py` — the rule
to its own module, the sink to its only consumer** (closed 2026-09-09; filed
2026-09-03). Shipped as `extract-unseeded-fold-module`.

`sink.py`'s own docstring advertises exactly four sink shapes
(`IntermediateSink`, `StatefulSink`, `TerminalSink`, `GeneratorBridgeSink`)
and never mentions the unseeded-fold trio it also carried — silence that
was itself the evidence the module had been holding a third, unaccounted-for
thing. `unseeded()` reaches two implementations of the same fold rule:
`UnseededSink` (a sink, used by `terminals.py`) and two dataclass boxes in
`collectors.py` (`_ExtremumBox`, `_ReduceBox`) that are deliberately *not*
sinks (design Decision 3 of `collapse-unseeded-accumulation-rule`), so no
base class could unify them. Inlining the rule at its call sites was
rejected on the same grounds before that decision — it had stood at five
duplicated sites, and `unseeded()` is the only mechanism that reaches both
halves.

The new module is `unseeded.py`, named for the concept directly rather than
as a container word — the same naming move `ordering.py` made for the
encounter-order vocabulary. `fold.py` was considered and rejected as
overclaiming a general-purpose fold utility this module doesn't provide;
`accumulation.py` likewise, since every collector in `collectors.py`
accumulates and only two of its boxes are unseeded.

**The trio did not travel together, and importer counts are what split it.**
`UNSET` has three importing modules and `unseeded()` two, but `UnseededSink`
has exactly one — `terminals.py`, where all three of its subclasses are also
defined. So `unseeded.py` holds the shared vocabulary alone, and the class
moved to `terminals.py` as `_UnseededSink`. This was the one point the
item's own reasoning got backwards: it had argued the trio was coherent
because `UnseededSink` *is* the concept (`_create_container() -> UNSET`,
`_finish(c) -> unseeded(c)`), which was a case built to rule `sink.py` **in**
against a move. Once the move was granted that argument no longer picked a
destination. Two things confirm the split. `unseeded.py` had imported
`TerminalSink` and `T` for the sole purpose of defining a class with one
consumer — a consumer that already imported `TerminalSink` itself — so the
move **added no import edge and removed both of `unseeded.py`'s**, leaving a
leaf with no package imports at all. And the underscore came back for the
right reason: `UnseededSink` was bare only because it crossed
`sink.py -> terminals.py`, so deleting the crossing makes it `_UnseededSink`
under CLAUDE.md's naming rule — the name
`collapse-unseeded-accumulation-rule` gave it before
`name-by-visibility-not-underscore` bared it. It also removed an asymmetry
the trio had hidden: the rule has two implementations that deliberately share
no base class, and keeping the sink beside the rule while the boxes sat in
`collectors.py` privileged one for no reason. Now the shared vocabulary is
central and each application sits with its consumer.

`sink.py` gains no pointer back, since after the move it has no relationship
to `unseeded.py` in either direction, and its docstring needed no edit — it
becomes accurate by subtraction of code, not by rewriting prose.

Three importers (`stream.py`, `terminals.py`, `collectors.py`) switched
their import of `UNSET`/`unseeded()` to `snakestream.unseeded`, keeping
whatever else they still needed from `sink.py` (`terminals.py`'s
`TerminalSink`, now used by `_UnseededSink` in place; `stream.py`'s
`Op`/`TerminalSink`). Two stale comments naming `sink.py` as
`UNSET`'s home (`stream.py`'s `_MISSING` contrast, and the equivalent in
`collectors.py`) were corrected to name `unseeded.py`. No behavior changed,
no test imported any of the three names, and no spec names them either, so
this was a zero-delta refactor (`skip_specs: true`).

Closes `sink-sentinel-placement`, gated on exactly this placement question
and resolved by exploration on 2026-09-09.
