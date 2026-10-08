+++
id = "collapse-unseeded-accumulation-rule"
title = "The unseeded-accumulation rule is stated once (`collapse-unseeded-accumulation-rule`)"
filed = 2026-09-03
closed = 2026-09-03
outcome = "shipped"
shipped_as = "collapse-unseeded-accumulation-rule"
+++

**`collapse-unseeded-accumulation-rule`** (2026-09-03) — the "an accumulation
that never saw an element finishes as `None`" rule, previously stated five
times with no site referencing another (`_ReduceSink._finish`,
`_MinMaxSink._finish` and `_FindSink._finish` in `terminals.py`; `_extremum()`
and `reducing()`'s `_finish` closures in `collectors.py`), now lives once as
`_unseeded()` beside `_UNSET` in `sink.py`, plus a `_UnseededSink` base
collapsing the shared `_create_container() -> _UNSET` hook the three sinks
also duplicated. No behaviour change and no spec delta (`skip_specs: true`) —
every capability that specifies the empty-source result already did, and
none of them changed.

The roadmap's open design question — whether `TerminalSink._finish`'s default
could carry the rule instead of a dedicated base — is answered, not left for
a later reader: it can, but shouldn't, because most `TerminalSink` subclasses
(`_CountSink`, `_ForEachSink`, `_MatchSink`, `_CollectorSink`,
`GeneratorBridgeSink`) can never hold `_UNSET`, and a universal default would
assert the rule on all of them regardless (design Decision 1).

It also takes a documented exception to the repository's recorded preference
against thin helpers (`_checked()` in `sort.py`, `ComparatorContractException`
are that preference applied): `_unseeded()` is a free function wrapping a
one-line check, which the preference says to inline. Kept anyway because no
other mechanism reaches all five sites — `collectors.py`'s two are closures
over dataclass boxes, not sinks, so `_UnseededSink` cannot reach them, and
without the function the collapse would be three sites out of five, leaving
the worse half of the problem (a rule stated in two separate modules) exactly
as it was (design Decision 3).

**A fresh finding surfaced by this change's exploration, priced and
declined, recorded so it is not re-derived:** `_sort_by_key`'s
`len(columns) == 1` lane is character-for-character the general lane at
`last = 0` — verified identical on 8,000 randomized cases, including ties
and null-tolerant `(present, key)` tuples, both directions. Collapsing it
costs ~0.2 us/sort of fixed `zip(*columns)` overhead on the lane every plain
`comparing()` call takes: +18.6% / +18.8% at n=4, noise-dominated by
n=20,000. Declined on measurement, not available work.

**Renamed by `name-by-visibility-not-underscore` (2026-09-03, below):**
`_UNSET` -> `UNSET`, `_unseeded()` -> `unseeded()`, `_UnseededSink` ->
`UnseededSink`, `_ReduceSink`/`_MinMaxSink`/`_FindSink` -> bare — every name
this entry introduced or read from was underscored while being imported by
another module in the package, the exact shape that change's rule forbids.
`_CountSink`/`_ForEachSink`/`_MatchSink`/`_CollectorSink` (named above as
never holding `UNSET`) are bare now too, for the same reason, unrelated to
this rule's Decision 1.
