## 1. Baseline

- [x] 1.1 Run `uv run pytest` and record the passing count and coverage figure — this is the regression signal for every behaviour-neutral task below, which must leave it unchanged apart from the two tests named in 2.3 and 3.4.

## 2. Cancellation before the first pull (the one behaviour change)

- [x] 2.1 Add a failing test first: a `Stream` chain `.peek(fn).limit(0)` over a non-empty source, asserting `fn` is never called and the result is empty. Add a second asserting the source generator itself is never pulled (a generator that appends to a list before each yield). Confirm both fail against the current tree.
- [x] 2.2 Guard the loop in `BaseStream._drive()` and `BaseStream._drive_to_sequential()` (`base_stream.py`): after `await head.begin(...)`, skip the `async for` entirely when `head.cancellation_requested()` is already `True`. Keep `await head.end()` outside the guard so the lifecycle still completes. Do **not** move the existing post-`accept()` check into the loop body (see design.md — Decision 2).
- [x] 2.3 Add `_LimitSink.begin()` (`ops.py`): call `super().begin(state_map)` first (that is what resolves `self._state`), then set `self._cancelled = self._state.value >= self._max_size`. Without this the 2.2 guard never fires, because `_cancelled` is currently only ever set inside `accept()`. Leave `accept()` byte-identical.
- [x] 2.4 Apply the same loop guard to `ParallelStream._drive_to()` (`parallel_stream.py`) — after `terminal.begin({})`, before composing/iterating.
- [x] 2.5 Add a sink-protocol-level test in `tests/test_sink.py`: a fake head sink reporting `cancellation_requested()` as `True` from `begin()` onwards, driven over a non-empty source, receives zero `accept()` calls and still receives `end()`.
- [x] 2.6 Add a `ParallelStream` case for `.limit(0)`, and a `limit(0)` case that pins the full `begin()`/`end()` lifecycle still running on a chain that pulled nothing.
- [x] 2.7 Run the full suite; every pre-existing test must still pass unmodified.

## 3. Rename `_sequential()` to a module-level `_wrap_sink()`

- [x] 3.1 Move `BaseStream._sequential()` to a module-level `_wrap_sink(intermediaries, terminal) -> Sink[Any]` in `base_stream.py`, body unchanged.
- [x] 3.2 Update its two call sites in `_drive()` and `_drive_to_sequential()`.
- [x] 3.3 Confirm no other reference survives: `grep -rn "_sequential" src/` should match only `_drive_to_sequential`.
- [x] 3.4 Update `tests/test_sequential.py:36` to import `_wrap_sink` from `snakestream.base_stream` and call it directly instead of `Stream.of([])._sequential(...)`.

## 4. Behaviour-neutral cleanups

- [x] 4.1 Drop the chain copies: `self._chain[:]` in `BaseStream._compose()` and `intermediaries[:]` in `ParallelStream._parallel()`.
- [x] 4.2 Rework `GeneratorBridgeSink` (`sink.py`) to drain in place — expose the buffer by name and clear it after yielding — and update both drain sites in `_drive()` to the guarded `if bridge.buffer: ... clear()` shape from design.md — Decision 3. Verify no allocation remains on the per-element path.
- [x] 4.3 Replace `to_generator()`'s hand-rolled `hasattr(composition, "aclose")` branch (`collector.py`) with `_maybe_aclosing` imported from `snakestream.base_stream`; collapse the duplicated loop body to one. Confirm `tests/test_collect.py`'s no-`aclose()`-source test still passes.
- [x] 4.4 Factor `BaseStream.sequential()`/`parallel()` onto a private `_handoff(cls)`, keeping each public method's local import and return annotation (design.md — Decision 5).
- [x] 4.5 Delete `Stream.__init__` (`stream.py`) and `ParallelStream.__init__` (`parallel_stream.py`) — both are pure `super().__init__` pass-throughs.
- [x] 4.6 Delete the redundant `self._check_not_consumed()` from `Stream.to_array()`; `collect()` already checks.
- [x] 4.7 Widen `Accumulator` in `type.py` to `Callable[[T, T | R], T | R | Awaitable[T | R]]`.

## 5. Spec and roadmap updates

- [x] 5.1 Edit `openspec/specs/pipeline-composition/spec.md`'s `## Purpose` paragraph directly, re-pointing its `_sequential()` reference to `_wrap_sink()` — a delta cannot change an existing capability's Purpose.
- [x] 5.2 Confirm the three delta specs in this change still match what was built; adjust wording only if an implementation decision moved.
- [x] 5.3 Move roadmap item 1 from **Now** to **Done** with a summary, noting the correction to its cancellation framing (only the pre-settled case over-pulled), and re-point any line references the remaining items carry into `base_stream.py`, `sink.py`, `stream.py`, `parallel_stream.py` and `collector.py`.
- [x] 5.4 Confirm no README edit is needed: every name touched is private except `Accumulator`, whose parity-table row names only the alias.

## 6. Verification

- [x] 6.1 `uv run pytest` — all pre-existing tests pass unmodified except `tests/test_sequential.py` (3.4); coverage at or above the 98% gate.
- [x] 6.2 `uv run ruff check .` and `uv run ruff format --check .`.
- [x] 6.3 `uv run ty check src` — in particular that the widened `Accumulator` and the `cast` in `_handoff`'s callers type-check clean.
- [x] 6.4 `openspec validate --changes batch-small-cleanups --strict`.
