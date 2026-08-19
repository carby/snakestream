## 1. Protocol bases in `sink.py`

- [x] 1.1 Add `Counter` (a `__slots__` mutable int box with a `value` attribute, defaulting to `0`) with a docstring saying it is an op's shared count as passed through the state map.
- [x] 1.2 Add `StatelessOp(Op)`: `__init__(*args)` storing `self._args`, `_sink_cls: ClassVar[Callable[..., Sink[Any]]]`, and `link(downstream)` returning `self._sink_cls(downstream, *self._args)`.
- [x] 1.3 Add `StatefulOp(Op)`: same shape, but `link()` passes `self` as the sink's second argument. Docstring on both classes stating that the axis is *shared* state (state crossing `ParallelStream`'s branches), not local buffering — so a buffering-but-unshared op like `sorted` is a `StatelessOp`.
- [x] 1.4 Add `StatefulSink(IntermediateSink[T])`: `__init__(downstream, op)` storing `self._op` and `self._state: Any = None`; `begin(state_map)` setting `self._state` to `state_map.get(self._op)`, or `self._op.make_shared_state()` when that is `None`, then awaiting `super().begin(state_map)`.

## 2. Collapse the stateless ops in `stream.py`

- [x] 2.1 Reduce `_FilterOp`, `_MapOp`, `_PeekOp`, `_FlatMapOp` to `class _XOp(StatelessOp): _sink_cls = _XSink`, deleting their `__init__` and `link()`. Leave every `*Sink` constructor signature as it is.
- [x] 2.2 Reduce `_SortedOp` the same way (two constructor args, `comparator` and `reverse`, both carried by `*args`).
- [x] 2.3 Run `uv run pytest` — the whole suite must pass unchanged at this point; nothing here alters behavior.

## 3. Collapse the stateful ops and sinks in `stream.py`

- [x] 3.1 Re-base `_DistinctSink` on `StatefulSink`: delete its `__init__` and `begin()` override, and read `self._state` in `accept()` instead of `self._seen`. `_DistinctOp` becomes a `StatefulOp` with `_sink_cls = _DistinctSink` and a one-line `make_shared_state()` returning `set()`.
- [x] 3.2 Re-base `_LimitSink` on `StatefulSink`: `__init__(downstream, op, max_size)` calls `super().__init__(downstream, op)` and keeps `self._max_size`/`self._cancelled`; delete its `begin()`; `accept()` and the reserve-before-await block read and increment `self._state.value`. Keep the race comment verbatim and keep the reservation before the `await`.
- [x] 3.3 `_LimitOp` becomes a `StatefulOp` with `_sink_cls = _LimitSink` and `make_shared_state()` returning `Counter()`.
- [x] 3.4 Re-base `_SkipSink`/`_SkipOp` the same way: `self._state.value` in place of `self._skipped[0]`, `make_shared_state()` returning `Counter()`.
- [x] 3.5 Grep `src/` for any surviving `[0]` index or `list[int]` annotation on limit/skip state, and for `self._seen`/`self._count`/`self._skipped`.

## 4. Verify

- [x] 4.1 `uv run pytest` — full suite green, coverage at or above the 98% gate.
- [x] 4.2 `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src`. If `ty` rejects the `_sink_cls(...)` call, confirm the annotation is `ClassVar[Callable[..., Sink[Any]]]` rather than `type[Sink[Any]]` (see design.md — Risks).
- [x] 4.3 Sanity-check that `parallel_stream.py` needed no edit: `_parallel()` still builds the state map by calling `make_shared_state()` on every op and keying non-`None` results.
- [x] 4.4 Run the standard benchmark harness (Python 3.14, 20,000 elements, chain of 8 `.map()` ops, best of 5) to confirm no per-element regression, plus one `.limit()`/`.skip()` chain covering the `Counter` swap. Record the figures; this is a sanity check, not a gate.

## 5. Tests

- [x] 5.1 Add a `tests/test_sink.py` case for the new spec requirement: a stateful sink begun with a state map holding no entry for its op ends up with state produced by that op's own factory — same type and initial value as `op.make_shared_state()` returns, and not the same object as any other sink's.
- [x] 5.2 Add a `Counter` case: fresh instances start at `0` and are independent; two sinks built from one op and given one state map increment the same `Counter`.
- [x] 5.3 Confirm the existing `Op` test doubles in `tests/test_sink.py` and `tests/test_sequential.py` still subclass `Op` directly and were not migrated onto the new bases (design.md — Test doubles).

## 6. Documentation

- [x] 6.1 Move the roadmap's op-collapse item from **Now** to **Done**, describing what landed and noting that the `ops.py` split (still in **Now**) is now unblocked and is a pure move.
- [x] 6.2 Confirm no README edit is needed — every name touched is private or unexported, and no public API or behavior changed.
