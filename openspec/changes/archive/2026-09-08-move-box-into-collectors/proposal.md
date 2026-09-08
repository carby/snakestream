## Why

`Box` is defined in `sink.py` and used by exactly one module: `collectors.py`,
in `counting()` alone, across four lines. `collectors.py` already holds nine
private containers of the same shape — `_SumBox`, `_AvgBox`, `_SummaryBox`,
`_ExtremumBox`, `_ReduceBox`, `_ToMapBox`, `_GroupBox`, `_MappingBox`,
`_CollectAndThenBox` — so the generic one is the tenth member of a family it
does not live with.

Nothing in `sink.py` uses it. `terminals.py` and `ops.py` mention it only in
prose explaining why they deliberately do *not* use it (`CountSink` owns its
container exclusively; `LimitOp`/`SkipOp`'s counter needs a lock `Box` has no
reason to carry). `Box`'s own docstring describes a mutable single-value
container and says nothing about `begin`/`accept`/`end`, which is what
`sink.py`'s docstring says the module is for.

This is the smallest and least contested third of the roadmap item
`sink-sentinel-placement`, which `extract-encounter-order-model` deferred as
"the natural follow-on" to its own move. That item bundled `Box` with `UNSET`
and `unseeded()` as one question; they are not one question, and the caller
counts are what separate them — `UNSET` has three importing modules,
`unseeded()` and `Box` have one each. `Box` is the only one of the three whose
home is decided by counting rather than by judgement, so it moves on its own.

## What Changes

- `Box` moves from `src/snakestream/sink.py` to `src/snakestream/collectors.py`,
  placed with the container family it belongs to.
- It is renamed `_Box`. This is not a separate decision: `collectors.py` becomes
  the only module that uses it, and the project's naming rule underscores a
  module-level name exactly when no other module in the package uses it.
  `tests/test_name_visibility.py` enforces the half of that rule a build check
  can decide.
- Three stale in-source references are corrected in the same change:
  - `sink.py`'s remaining `UNSET` comment, which currently justifies a group
    placement for names that no longer sit together.
  - `terminals.py`'s `CountSink` docstring ("A plain int, not a `Box`...").
  - `ops.py`'s `LimitOp`/`SkipOp` state docstring ("Kept out of `Box`
    (`sink.py`)...").

No behaviour changes: the same class, the same call sites, the same four lines
in `counting()`. The move is provable by inspection.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. No spec in `openspec/specs/` names `Box`, `UNSET` or `unseeded()` —
`sink-protocol` describes the push protocol and its shapes, not the containers
a collector accumulates into. This change alters module placement and one
name's visibility, both of which are implementation structure, so it sets
`skip_specs: true` rather than inventing a requirement to satisfy validation.

`internal-name-visibility` is *satisfied* by the rename rather than modified by
it: the rule already says what `_Box` should be called once `collectors.py` is
its only user, and the existing build check already enforces it.

## Impact

- `src/snakestream/sink.py` — `Box` removed, one import-topology comment
  corrected. `UNSET` and `unseeded()` stay; where they belong is the remaining
  half of `sink-sentinel-placement` and is deliberately untouched here.
- `src/snakestream/collectors.py` — gains `_Box`, drops it from its
  `from snakestream.sink import ...` line, and rewrites `counting()`'s four
  references.
- `src/snakestream/terminals.py`, `src/snakestream/ops.py` — comment text only.
- `tests/` — any test importing `Box` from `snakestream.sink` follows the move;
  `tests/test_name_visibility.py` should stay green without modification, and
  a red result there means the rename was done wrong rather than that the test
  needs changing.
- Not in scope: `UNSET`'s dual role as both an accumulation seed and an
  arity-dispatch sentinel, tracked as its own roadmap item.
