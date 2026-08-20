## Why

Roadmap item 1 (**Now**, no dependencies). A hash of the function bodies on
2026-08-19 confirmed that `collector.py` carries literal copies: `summing_int`
and `summing_long` are byte-identical, `averaging_int`/`averaging_long`/
`averaging_double` are all three byte-identical, and `summing_double` differs
from the summing pair only by a `0.0` seed and a `float()` cast. `grouping_by`
and `partitioning_by` are the same function twice over. Eight sinks across
`ops.py` and `terminals.py` open `__init__` with the same three-line dispatch
triple, and `StatelessOp`/`StatefulOp` in `sink.py` duplicate their `__init__`
and `_sink_cls` declaration to differ by one line of `link()`.

Now, because all four parts are behavior-neutral and touch private names only,
and because part (c) shrinks the surface that roadmap item 2 — the `Collector`
redesign — has to rewrite.

## What Changes

- **(a) Collapse the six summing/averaging bodies.** Add a private
  `_summing(seed, coerce)` and a private `_averaging()`; `summing_int`,
  `summing_long`, `summing_double`, `averaging_int`, `averaging_long` and
  `averaging_double` become thin wrappers. The six public names stay, and so
  does the `collector.py:65-69` comment defending them — Java distinguishes by
  primitive, Python's numeric tower does not. That comment defends keeping six
  *names*; it has been read as defending six *bodies*, which it never did. It
  is reworded to say so.
- **(b) Hoist the sink dispatch triple to a shared mixin.** `_FilterSink`,
  `_MapSink` and `_PeekSink` (`ops.py`) and `_ForEachSink`, `_ReduceSink`,
  `_MinMaxSink`, `_MutableReductionSink` and `_MatchSink` (`terminals.py`) all
  store a callable and then classify it: `is_async_callable(fn)` into
  `self._is_async`, plus `self._checked = False`. One small mixin in
  `callable_dispatch.py` does it once, storing the callable as `self._fn` — so
  the eight sinks stop naming it five different ways (`_predicate`, `_mapper`,
  `_consumer`, `_accumulator`, `_comparator`) and their `accept()` bodies
  become structurally identical, which is what makes the canonical-shape
  comment in that module checkable rather than aspirational. Each `accept()`
  body keeps its inlined dispatch **shape** unchanged — the only edit inside
  one is the mechanical attribute rename, which costs the same single
  attribute lookup it did before. No call is added to the per-element path.
- **(c) Factor `grouping_by`/`partitioning_by` onto one helper.** Both classify
  elements into a `dict` of lists using the same five-branch dispatch, then map
  `downstream` over the values; they differ only in classifier-vs-
  `bool(predicate(...))` and in partitioning's pre-seeded `{True: [], False:
  []}`. One private `_group_into(composition, key_fn, initial)` covers both.
- **(d) Make `StatefulOp` subclass `StatelessOp`** (`sink.py:56-89`), inheriting
  `__init__` and `_sink_cls` and overriding `link()` alone. Both docstrings are
  kept — they draw a real distinction about shared state that the class
  hierarchy does not express.
- No public API change. Every name introduced is private; the only public names
  touched are the six summing/averaging collectors, whose signatures, return
  types and behavior are unchanged. No README edit.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None — this change sets `skip_specs: true`. All four parts are pure
refactors: no requirement in `collector-counting-summing-averaging`,
`collector-grouping-by`, `collector-partitioning-by`, `callable-dispatch`,
`sink-protocol` or `terminal-sinks` changes, because no externally observable
behavior does. The existing suite is the contract these collapses must hold.

## Impact

- `src/snakestream/collector.py` — parts (a) and (c). Shrinks most; ~90 lines
  from (a) alone, roughly 150 net across the change.
- `src/snakestream/ops.py`, `src/snakestream/terminals.py` — part (b),
  `__init__` bodies only.
- `src/snakestream/sink.py` — part (d), plus the new dispatch mixin if it lands
  here rather than in `callable_dispatch.py` (a design.md decision).
- `tests/` — no behavior change to cover, so no new tests are required by the
  change itself; the existing 457 tests are the regression gate, and the 98%
  coverage floor must still hold after the collapse (fewer lines, same
  branches).
- **Hot-path constraint.** Part (b) is specifically the slice of the rejected
  `add-callsite-dispatch` change that the benchmark did *not* rule out: that
  was rejected for putting a *call* on the per-element `accept()` path
  (measured +32-75%). This touches `__init__` only, so per-element attribute
  lookups stay identical and the cost is zero. This change must not drift into
  re-litigating the per-element shape.
- No dependency, tooling or CI changes.
