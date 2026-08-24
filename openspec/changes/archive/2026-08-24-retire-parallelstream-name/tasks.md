## 1. Spec deltas (requirement text)

- [x] 1.1 Apply this change's `specs/stream-foreach-ordered/spec.md` delta to `openspec/specs/stream-foreach-ordered/spec.md`: rename the "for_each_ordered() preserves encounter order on ParallelStream" requirement and its scenario to the `RACING`/`.parallel()` wording.
- [x] 1.2 Apply this change's `specs/pipeline-composition/spec.md` delta to `openspec/specs/pipeline-composition/spec.md`: reword the "Parallel skip() remains globally correct across branches" and "Parallel branches serialize pulls from the shared upstream source" requirements to reference `RACING` execution and `race_through()` instead of `ParallelStream`/`._parallel()`/`._compose()`.

## 2. Purpose sections (direct edits, no delta — OpenSpec ignores MODIFIED against Purpose)

- [x] 2.1 `openspec/specs/pipeline-composition/spec.md` — reword Purpose's "in both `Stream` (sequential) and `ParallelStream` (parallel, where state must additionally stay globally correct across racing branches within one composition)" to describe `SEQUENTIAL`/`RACING` executors instead of the two classes.
- [x] 2.2 `openspec/specs/stream-close-handling/spec.md` — reword Purpose's "shared by `BaseStream`, `Stream`, and `ParallelStream`" to drop the retired class name (close handlers are shared by every stream instance regardless of executor).
- [x] 2.3 `openspec/specs/terminal-sinks/spec.md` — reword Purpose's "an ordered `ParallelStream.find_first()`" to "an ordered `find_first()` under `RACING` execution".
- [x] 2.4 `openspec/specs/stream-find-first/spec.md` — reword Purpose's "Defines `find_first()`'s contract on `Stream` and `ParallelStream`... for choosing an ordered vs. racing pull strategy on a `ParallelStream`" to describe the `SEQUENTIAL`/`RACING` executor choice instead.
- [x] 2.5 `openspec/specs/stream-foreach-ordered/spec.md` — reword Purpose's "even when called on a `ParallelStream` instance whose racing-branch execution model does not otherwise preserve order" to reference `RACING` execution instead of a `ParallelStream` instance.
- [x] 2.6 `openspec/specs/generic-stream-typing/spec.md` — reword Purpose's "the element type flowing through a `Stream`/`ParallelStream` pipeline" to "a `Stream` pipeline, regardless of execution mode".
- [x] 2.7 `openspec/specs/stream-ordering/spec.md` — reword Purpose's "it does not itself alter iteration order in `Stream` or `ParallelStream`" to drop the retired class name in favor of executor-mode wording.
- [x] 2.8 `openspec/specs/mutable-reduction-collect/spec.md` — reword Purpose's "Applies identically to `Stream` (sequential) and `ParallelStream` (parallel) composition" to "Applies identically under `SEQUENTIAL` and `RACING` execution".
- [x] 2.9 `openspec/specs/pipeline-immutability/spec.md` — reword Purpose's "treating `Stream`/`ParallelStream` instances as immutable" to "treating stream instances as immutable" (mode switches already covered by `sequential()`/`parallel()` wording later in the same sentence).
- [x] 2.10 `openspec/specs/stream-iterator/spec.md` — reword Purpose's "Applies identically to `Stream` (sequential) and `ParallelStream` (parallel) composition" to "Applies identically under `SEQUENTIAL` and `RACING` execution".

## 3. Scenario titles (direct edits to the main specs, not deltas)

- [x] 3.1 `openspec/specs/stream-to-array/spec.md` — rename scenario "Works on `ParallelStream`" (line 22) to "Works under RACING execution"; update its WHEN/THEN body if it still names `ParallelStream`.
- [x] 3.2 `openspec/specs/stream-iterator/spec.md` — rename scenario "iterator() on a ParallelStream" (line 25) to "iterator() under RACING execution"; update its body accordingly.
- [x] 3.3 `openspec/specs/generic-stream-typing/spec.md` — rename scenario "ParallelStream inherits the element type" (line 14) to "A RACING stream inherits the element type"; update its THEN clause, which already explains the `ParallelStream` name was never exported.

## 4. Docstrings (src/, no behaviour change)

- [x] 4.1 `src/snakestream/callable_dispatch.py:56` — reword "leaks across compositions or across a ParallelStream's racing branches" to reference `RACING`'s racing branches instead of the retired class.
- [x] 4.2 `src/snakestream/sink.py:61` — reword the `ParallelStream` reference in `Op.make_shared_state`'s docstring to `RACING`.
- [x] 4.3 `src/snakestream/sink.py:77` — reword the `ParallelStream`'s racing branches reference to `RACING`'s racing branches.
- [x] 4.4 `src/snakestream/sink.py:92` — reword the `ParallelStream` reference in `StatefulOp`'s docstring to `RACING`.
- [x] 4.5 `src/snakestream/sink.py:188` — reword "each ParallelStream branch has its own bridge" to "each RACING branch has its own bridge".

## 5. Verification

- [x] 5.1 `grep -rn ParallelStream openspec/specs/ src/` returns no matches (test files and roadmap/README history are out of scope for this change — see proposal.md Impact).
- [x] 5.2 `openspec validate --change retire-parallelstream-name --strict` passes.
- [x] 5.3 `uv run pytest` — full suite green, no test file edited (docs/docstrings-only change).
- [x] 5.4 `uv run ruff check .` and `uv run ruff format --check .` pass.
