+++
id = "extract-args-op-base"
title = "Extracted a neutral `_ArgsOp` base for `StatelessOp`/`StatefulOp`"
filed = 2026-08-24
closed = 2026-08-24
outcome = "shipped"
+++

**Extracted a neutral `_ArgsOp` base for `StatelessOp`/`StatefulOp`**
(2026-08-24). `StatefulOp`'s docstring spent a paragraph disclaiming its own
base class — "Subclassing `StatelessOp` is a mechanical convenience ... It
does not mean a stateful op is a kind of stateless one" — while the two
classes shared only `__init__` and the `_sink_cls` `ClassVar` declaration
and differed solely in `link()`. When a class docstring has to argue
against the hierarchy it sits in, the hierarchy is misleading the reader,
not the docstring.

`sink.py` now has `_ArgsOp(Op)` holding the shared `__init__(self, *args)`
and `_sink_cls` declaration, with `StatelessOp(_ArgsOp)` and
`StatefulOp(_ArgsOp)` as siblings, each defining only its own `link()`.
`StatefulOp` no longer subclasses `StatelessOp`, so the disclaimer
paragraph is deleted rather than kept — its docstring now only explains
what shared state is and how a subclass declares it. Both names stay
importable and subclassable exactly as before, which is what
`tests/test_sink.py`'s existing imports and subclasses of both exercise.

Pure structural refactor, scoped to `sink.py`'s `Op` hierarchy alone;
`ops.py`'s op definitions and every caller of `link()`/construction are
unaffected. `skip_specs: true`: no spec-level behavior changed, only where
two private class declarations sit in the hierarchy. 535 tests green with
**no test file edited**; `ruff`, `ruff format --check` and `ty check src`
all pass. Off the per-element path (`Op` construction and `link()` run once
per composition, never per element), so no benchmark gate applied. See
`openspec/changes/extract-op-base-class`.
