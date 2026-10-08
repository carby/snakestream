+++
id = "introduce-op-abc"
title = "Introduced an `Op` ABC and typed the chain against it"
filed = 2026-08-19
closed = 2026-08-19
outcome = "shipped"
+++

**Introduced an `Op` ABC** (`sink.py`) and typed the chain against it,
completing the op/sink protocol the Sink-chain redesign left half-specified.
`Op` has one abstract member, `link(downstream) -> Sink`, and one concrete
`make_shared_state() -> Any` returning `None`; all eight shipped ops
(`_FilterOp`, `_MapOp`, `_PeekOp`, `_SortedOp`, `_FlatMapOp`, `_DistinctOp`,
`_LimitOp`, `_SkipOp`) now subclass it, the three stateful ones keeping their
`make_shared_state()` overrides unchanged.

`_chain`, `_derive`, `_sequential`, `_drive` and `ParallelStream._parallel`
are typed `list[Op]` instead of `list[Any]`, so `ty` — gated in CI on the
3.14 leg — can now see the pipeline's central data structure. The
`getattr(op, "make_shared_state", None)` sniff in `parallel_stream.py` is
gone, replaced by an unconditional call keying the state map only on a
non-`None` result; `None` is now a specified contract meaning "no shared
state", so a stateful op returns a container and never `None`.

Behavior-neutral by construction: no method body was edited and no public API
changed (`Op` is not exported, and all eight op classes stay private), so
README's parity tables need no edit. 415 tests pass at 98.58% coverage. The
existing op test doubles in `tests/test_sink.py` and `tests/test_sequential.py`
were made to subclass `Op` so they stay faithful to the protocol. See
`openspec/changes/archive/2026-08-19-introduce-op-abc`.

**Unblocks** the op-class-collapse item still in **Now** — the shared
`*args`/`_sink_cls` base that item wants now has a typed base class to hang
off, and the `StatefulSink` base it also wants can rely on every op having a
`make_shared_state()` to key against.
