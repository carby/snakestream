## Why

The Sink-chain redesign shipped eight op/sink pairs written out longhand, and
the `Op` ABC that followed typed them without touching their bodies. What is
left is seven `*Op` classes (`_FilterOp`, `_MapOp`, `_PeekOp`, `_SortedOp`,
`_FlatMapOp`, `_LimitOp`, `_SkipOp`) that are the same three lines each — hold
the constructor arguments, hand them to a sink — and three stateful sinks that
each retype the same state-map lookup by hand. The duplication is the kind that
only grows: every future intermediate op copies it again.

Two smaller defects ride along in the same code. The state-map lookup is
written as `state_map[self._op] if self._op in state_map else <default>` at
three sites (`stream.py:191`, `:218`, `:257`) where `state_map.get(...)` says
it in one clause, and its `<default>` literal duplicates what the op's own
`make_shared_state()` already returns — two independent statements of the same
state shape, free to drift. And `_LimitSink._count` / `_SkipSink._skipped` are
one-element `list[int]`s used as mutable boxes, so the subtlest code in the
file — `_LimitSink.accept`'s reserve-before-await race (`stream.py:225-231`) —
has to be read through `self._count[0] >= self._max_size`.

Doing this now also sequences correctly: it is unblocked by the `Op` ABC that
just landed, and the next roadmap item (splitting the op/sink definitions into
`ops.py`) wants the op half already shrunk so that move is a move and not a
move-plus-rewrite.

## What Changes

- Add two `Op` subclasses in `sink.py` — one for ops with no shared state, one
  for ops with — that store `*args` and forward them to a class-level
  `_sink_cls`. The seven listed `*Op` classes collapse to a base plus a class
  attribute each; `_DistinctOp` (no constructor arguments) joins the stateful
  base for its state factory.
- Add a `StatefulSink` base in `sink.py` holding the originating `Op` and
  resolving its state in `begin()` via `state_map.get(op)`, falling back to
  `op.make_shared_state()` — so an op declares the shape of its state exactly
  once, and a sink's local fallback state is by construction the same shape as
  the state it would have shared. `_DistinctSink`, `_LimitSink` and `_SkipSink`
  drop their hand-written `begin()` overrides.
- Add a small named mutable counter type, replacing the one-element-list boxes
  in `_LimitSink`/`_SkipSink` and in `_LimitOp`/`_SkipOp`'s
  `make_shared_state()`.
- No public API change. Every affected name is private (`_*Op`, `_*Sink`) or
  unexported (`Op`, `Sink`, `IntermediateSink`, and the new bases), so README's
  parity tables and migration log need no edit, and no behavior a user can
  observe changes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `sink-protocol`: the **Shared state is delivered through begin** requirement
  currently says only that a sink with no entry in the state map "SHALL
  initialize fresh state local to itself". This change makes that fallback
  concrete and binding: the local fallback SHALL be produced by the same
  operation-level factory that produces shared state, so shared and local state
  are the same shape and a sink never carries a second, independently-written
  statement of what its state is.

## Impact

- `src/snakestream/sink.py` — new stateless/stateful `Op` bases, new
  `StatefulSink`, new counter type. Grows; it is the protocol module and these
  are protocol-level bases.
- `src/snakestream/stream.py` — the eight op classes shrink to declarations;
  the three stateful sinks lose their `begin()` overrides and read their state
  through one attribute.
- `src/snakestream/parallel_stream.py` — unchanged: it already calls
  `make_shared_state()` unconditionally and keys only on a non-`None` result.
- `tests/test_sink.py`, `tests/test_sequential.py` — hold `Op` test doubles;
  they subclass `Op` directly and should continue to, since the point of the
  doubles is fidelity to the protocol rather than to the convenience bases.
  New coverage is needed for the shared/local state-shape guarantee and for the
  counter type.
- No dependency, tooling, or CI changes.
