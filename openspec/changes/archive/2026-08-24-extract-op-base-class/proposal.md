## Why

`sink.py:90-106`'s `StatefulOp` docstring spends a paragraph disclaiming its
own base class: "Subclassing `StatelessOp` is a mechanical convenience ... It
does not mean a stateful op is a kind of stateless one." `StatelessOp` and
`StatefulOp` share only `__init__` and the `_sink_cls` `ClassVar` declaration
and differ solely in `link()`. When a class docstring has to argue against
the hierarchy it sits in, the hierarchy is misleading the reader, not the
docstring. This is Roadmap **Now** item 1 of the 2026-08-24 legibility batch.

## What Changes

- Add a neutral `Op` subclass (e.g. `_ArgsOp`) in `sink.py` holding the
  `__init__(self, *args)` and `_sink_cls: ClassVar[...]` that `StatelessOp`
  and `StatefulOp` currently duplicate via inheritance-of-convenience.
- `StatelessOp` and `StatefulOp` become siblings under that base, each
  defining only its own `link()`. `StatefulOp` no longer subclasses
  `StatelessOp`, so its docstring's disclaimer is deleted rather than kept.
- Both `StatelessOp` and `StatefulOp` remain importable under their current
  names with their current public shape — `tests/test_sink.py` imports and
  subclasses both directly and must not need edits.
- No behaviour change: `link()`'s output for both classes is identical
  before and after, this is purely a restructuring of where `__init__` and
  `_sink_cls` are declared.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None — pure internal refactor. `skip_specs: true` is set in this change's
`.openspec.yaml` since no spec-level (observable) behavior changes, only
where two private class declarations sit in `sink.py`'s hierarchy.

## Impact

- `src/snakestream/sink.py`: `StatelessOp`/`StatefulOp` restructured under a
  new private base class; `StatefulOp`'s docstring simplified.
- No public API change (`StatelessOp`, `StatefulOp` are already private-ish,
  imported only by tests and by `ops.py`'s op definitions, both of which use
  only `link()` and construction — unaffected).
- `tests/test_sink.py` must pass with no edits (the batch's tripwire: full
  suite green with no test file touched).
- Off the per-element path — `Op`/`link()` run once per composition, never
  per element — so no benchmark gate applies.
