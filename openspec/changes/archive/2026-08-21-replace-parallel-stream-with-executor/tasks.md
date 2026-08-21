The usual "green with no test edited" tripwire cannot apply here — the
behaviour change is the point. Its replacement, used throughout: **every test
outside the four identified multi-line chains must pass untouched**, verified by
diff, not by judgement. Groups 1 and 2 are preparation and can land findings
before any restructuring begins.

## 1. Measure first, so the protocol's one asymmetry carries a current number

- [x] 1.1 Benchmark the fused sequential terminal drive against the generic
      compose-then-drain form on the established harness (Python 3.14.5, 20,000
      elements, best of 5, three independent invocations), on a
      terminal-dominated variant with no intermediate chain: `count()` and
      `reduce(acc)` sync at minimum.
- [x] 1.2 Record the figures in `design.md` under Decision 1. If the fused form
      is inside noise, **take the simplification**: drop `feed_through`, let
      `Sequential` inherit the generic `value()`, and strike the override from
      the design and from the `stream-execution-model` spec's "MAY override"
      allowance. If it is outside noise, keep the override and cite the number
      in its docstring.

## 2. Pin the four behaviour-changing test sites before touching source

- [x] 2.1 For each of `tests/test_close.py:45`, `tests/test_close.py:68`,
      `tests/test_sequential.py:46`, `tests/test_parallel.py:158`, write down in
      the change what runs raced before and after, and whether the existing
      assertion still holds. No source edits yet.
- [x] 2.2 Confirm the two mid-chain-mode-switch tests
      (`test_sequential.py:46`, `test_parallel.py:158`) are testing a concept
      this change retires, and draft what each should assert instead — that the
      executor in force at the terminal governs the whole pipeline.
- [x] 2.3 Record the full `.parallel()`/`.sequential()` call-site inventory (51
      sites) so step 6.1's diff check has a baseline.

## 3. The execution module

- [x] 3.1 Create `src/snakestream/execution.py` importing only from `sink.py`,
      and move `PROCESSES` into it.
- [x] 3.2 Move `_drive` in as `stream_through(chain, source, state_map=None)`
      and `_parallel`'s body in as `race_through(chain, source, workers)`, both
      as free functions taking no `self`. Keep `_guarded()` and the race loop
      byte-for-byte apart from the `self._drive` reference becoming a direct
      call to `stream_through`.
- [x] 3.3 Move `_drive_to_sequential`'s body in as
      `feed_through(chain, source, terminal)` and add `drain(gen, terminal)`
      wrapping `_copy_into` plus `.result()`. Skip this task's `feed_through`
      half if 1.2 said to drop it.
- [x] 3.4 Add the `Executor` protocol: abstract `elements()`, concrete generic
      `value()` returning `drain(self.elements(...), terminal)`. Add
      `SEQUENTIAL` (with the `value()` override, if kept) and `Racing(workers)`.
      Give each an `is_parallel` class attribute.
- [x] 3.5 `uv run ty check src` and the full suite must still pass — nothing
      references the new module yet, so this is a pure-addition checkpoint.

## 4. Rewire the stream onto the executor

- [x] 4.1 Add the `_executor` field to `BaseStream.__init__`, defaulting to
      `SEQUENTIAL`, and carry it in `_derive()` alongside `_ordered` and the
      close handlers.
- [x] 4.2 Replace `_compose()`'s body with
      `self._executor.elements(self._chain, self._stream)` and add `_evaluate()`
      as `await self._executor.value(self._chain, self._stream, terminal)`.
- [x] 4.3 Repoint every terminal in `stream.py` from `_drive_to(...)` to
      `_evaluate(...)`, and `for_each_ordered()` from `_drive_to_sequential(...)`
      to an explicit `SEQUENTIAL.value(...)`.
- [x] 4.4 Unify `find_first()`: one implementation on `Stream` that returns
      `await self.find_any()` when not ordered and drives under an explicit
      `SEQUENTIAL` otherwise. Delete the `ParallelStream` override.
- [x] 4.5 Delete `_drive`, `_drive_to`, `_drive_to_sequential` and `_parallel`
      from the stream classes. `_wrap_sink` and `_copy_into` stay module-level in
      `base_stream.py` — `test_sequential.py` imports `_wrap_sink`.
- [x] 4.6 Make `is_parallel()` read `self._executor.is_parallel`.

## 5. The behaviour change: position-independent mode switches

- [x] 5.1 Replace `_handoff(cls)` with `_derive_executor(executor)`: a new
      instance via `type(self)` carrying the **same source and same chain**, the
      new executor, and the ordering flag and close handlers, marking the
      receiver consumed. It MUST NOT compose, and MUST NOT assign onto `self`
      and return `self` — see design.md Decision 3 and the
      `pipeline-immutability` delta.
- [x] 5.2 Point `sequential()`/`parallel()` at it and delete both function-local
      imports and the `stream.py` <-> `parallel_stream.py` import cycle.
- [x] 5.3 Delete `src/snakestream/parallel_stream.py`.
- [x] 5.4 Verify the subclass-identity fix with a `class MyStream(Stream)` that
      carries an attribute: it must survive `.parallel()` and `.sequential()`.
      This is the live bug the change fixes; it needs a test.
- [x] 5.5 Re-run the placement probe from the proposal: `.map(slow).parallel()`
      and `.parallel().map(slow)` must now both complete in roughly `N/workers x
      delay`. This is the acceptance check for the semantics change.

## 6. Tests

- [x] 6.1 Run the full suite. Diff the test tree: **only** the four files from
      group 2 may differ. Anything else that needed editing is a regression, not
      a migration — investigate before changing it.
- [x] 6.2 Rewrite the two mid-chain-switch tests per 2.2.
- [x] 6.3 Add coverage for the new capability: executor carried through
      intermediate ops; `for_each_ordered`/`find_first` ignoring the stream's
      executor; a stateful op declared *before* `.parallel()` staying globally
      correct (the newly reachable path in `pipeline-composition`); a mode
      switch not composing (the queued chain survives it).
- [x] 6.4 Coverage gate: `uv run pytest --cov-fail-under=98`.

## 7. Docs and close-out

- [x] 7.1 README migration-log entry for the `.parallel()`/`.sequential()`
      semantics change. It must say plainly that this one **breaks silently** —
      results are unchanged, only which ops run raced changes — and give the
      remedy for a caller who placed `.parallel()` late on purpose: split into
      two streams.
- [x] 7.2 Rewrite CLAUDE.md's "Sequential vs. parallel execution" section, which
      currently describes `ParallelStream` subclassing `Stream` and overriding
      `_compose()`. Check the "chain-of-closures" section too — it names
      `_compose()` as the seam where mode is decided.
- [x] 7.3 Check the README API table for rows describing `.parallel()` /
      `.sequential()` / `is_parallel()` behaviour that the semantics change
      invalidates.
- [x] 7.4 `uv run ruff check .`, `uv run ruff format --check .`,
      `uv run ty check src`, `openspec validate replace-parallel-stream-with-executor --strict`.
- [x] 7.5 Move the roadmap item from **Later** to **Done**, recording the
      measurement from 1.2, the position-dependence finding with its figures, and
      the `BaseStream`/`Stream` collapse left open as a follow-up.
