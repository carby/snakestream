+++
id = "collapse-op-classes-onto-bases"
title = "Collapsed the eight op classes onto shared bases"
filed = 2026-08-19
closed = 2026-08-19
outcome = "shipped"
+++

**Collapsed the eight op classes onto shared bases.** `sink.py` gained
`StatelessOp` and `StatefulOp` — both storing the arguments the op was
constructed with and forwarding them to a class-level `_sink_cls`, the
stateful one also passing `self` so its sink can key the state map — plus a
`StatefulSink` base and a `Counter` value type. All eight ops are now
declarations: five are two lines (`class _MapOp(StatelessOp): _sink_cls =
_MapSink`), three add a one-line `make_shared_state()`. `stream.py` went from
537 to 485 lines and `_DistinctSink`/`_LimitSink`/`_SkipSink` lost their
hand-written `begin()` overrides.

The state-map lookup written out at three sites became one `state_map.get()`
in `StatefulSink.begin()`, and its fallback now comes from the op's own
`make_shared_state()` rather than a literal retyped in the sink — so an op's
state shape is stated exactly once and shared and local state cannot drift.
That guarantee was added to the `sink-protocol` spec as a new scenario under
**Shared state is delivered through begin**, the change's only spec delta.
`_LimitSink._count: list[int]` and `_SkipSink._skipped: list[int]` became a
`Counter` with a `value` attribute, so the reserve-before-await race block
now reads `self._state.value >= self._max_size`.

Naming follows Java's `StatelessOp`/`StatefulOp`, with the class docstrings
pinning that the axis here is *shared* state — state crossing
`ParallelStream`'s branches — not local buffering, which is why the
whole-stream-buffering `_SortedOp` is a `StatelessOp`.

Behavior-neutral and no public API change; every name touched is private or
unexported, so README needed no edit. `parallel_stream.py` needed no edit
either — it already called `make_shared_state()` unconditionally and keyed
only non-`None` results. 421 tests pass at 99% coverage (six new: the
factory-sourced fallback, `Counter` independence, shared-counter increment
across two sinks from one op, and argument forwarding through both bases).
Two existing tests were touched: `test_op_protocol.py`'s fresh-container
assertion asserted emptiness as `first in ([0], set())`, which named the old
list representation, and two test-local doubles (`_StatelessOp`,
`_StatefulOp`/`_StatefulSink`) were renamed to `_LinkOnlyOp` and
`_TallyingOp`/`_TallyingSink` since their names now collide with the real
protocol classes. The doubles still subclass `Op`/`IntermediateSink`
directly, deliberately: their job is to pin the protocol, not the
convenience bases.

**Benchmark (2026-08-19, same harness: Python 3.14.5, 20,000 elements, best
of 5, interleaved before/after rounds to control for machine drift):** 8×
`.map()` 1935–2026 ns/element before, 2001–2071 after; `.skip(1).limit(n)`
1081–1120 before, 1037–1145 after. Run-to-run spread within either condition
(±5–8% on this WSL2 box) exceeds the gap between them, and the 8× `.map()`
path's per-element code is byte-identical across the change — everything the
change touches per element is the `Counter` attribute load replacing a list
index, and everything else (`link()`, `begin()`) runs once per composition.
No measurable regression.

**Unblocks** the `ops.py` split still in **Now**, which is now a pure move.
See `openspec/changes/collapse-op-classes`.
