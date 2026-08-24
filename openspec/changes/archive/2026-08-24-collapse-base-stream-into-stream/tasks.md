## 1. Merge BaseStream into Stream

- [x] 1.1 Copy `BaseStream`'s state and methods (`__init__`,
  `_check_not_consumed`, `_derive`, `_compose`, `_evaluate`,
  `_derive_executor`, `sequential()`, `parallel()`, `iterator()`,
  `unordered()`, `is_ordered()`, `on_close()`, `close()`, `is_parallel()`)
  into `src/snakestream/stream.py`, ahead of `Stream`'s existing static
  factories, verbatim except updating `class BaseStream(Generic[T]):` to
  `class Stream(Generic[T]):` and dropping the now-redundant `class
  Stream(BaseStream[T]):` line.
- [x] 1.2 Update `stream.py`'s imports: add `Generic` from `typing`; drop
  `from snakestream.base_stream import BaseStream`; add
  `from snakestream.execution import RACING, SEQUENTIAL, Executor,
  _wrap_sink as _wrap_sink` and the other names `base_stream.py` imported
  that `stream.py` doesn't already (`IllegalStateException`,
  `AsyncIterable`, `CloseHandler`, `Op`, `TerminalSink`), reconciling with
  `stream.py`'s existing import list rather than duplicating any entry
  already present. Deviation: `_wrap_sink` was not imported into
  `stream.py` — it is a re-export `base_stream.py` carried purely for
  `test_sequential.py`'s convenience, unused by any code in `stream.py`
  itself; task 2.1 repoints that one caller directly at
  `snakestream.execution`, so importing it here would be dead code
  (confirmed via `ruff check`, which passes clean without it).
- [x] 1.3 Move `_normalize()` and `_accept()` (module-level helpers used
  only by `BaseStream.__init__`) into `stream.py` alongside the merged
  `__init__`.
- [x] 1.4 Delete `src/snakestream/base_stream.py`.
- [x] 1.5 Verify the merged methods are byte-identical to their pre-change
  form (modulo the class-line change) by diffing against `git show
  HEAD:src/snakestream/base_stream.py` before the file is removed from the
  index.

## 2. Fix the one test import

- [x] 2.1 `tests/test_sequential.py`: change
  `from snakestream.base_stream import _wrap_sink` to import `_wrap_sink`
  from its defining module, `snakestream.execution`.

## 3. Spec deltas (requirement text)

- [x] 3.1 Apply this change's `specs/generic-stream-typing/spec.md` delta to
  `openspec/specs/generic-stream-typing/spec.md`: reword "Stream classes are
  parameterized by element type" to describe `Stream` alone.
- [x] 3.2 Apply this change's `specs/stream-close-handling/spec.md` delta to
  `openspec/specs/stream-close-handling/spec.md`: reword the three
  `BaseStream`-referencing requirements to `Stream`.
- [x] 3.3 Apply this change's `specs/stream-ordering/spec.md` delta to
  `openspec/specs/stream-ordering/spec.md`: rename and reword "BaseStream
  tracks an ordered/unordered flag defaulting to ordered" and "BaseStream.
  unordered() marks the stream as not order-dependent"; reword "The ordering
  flag survives sequential()/parallel() mode switches".
- [x] 3.4 Apply this change's `specs/pipeline-composition/spec.md` delta to
  `openspec/specs/pipeline-composition/spec.md`: reword "Building a composed
  pipeline does not recurse per chained operation" from `BaseStream._compose()`
  to `Stream._compose()`.
- [x] 3.5 Apply this change's `specs/stream-iterator/spec.md` delta to
  `openspec/specs/stream-iterator/spec.md`: rename "BaseStream.iterator()
  exposes the composed pipeline without consuming it" to "iterator() exposes
  the composed pipeline without consuming it"; reword the other two
  requirements' bodies from `BaseStream.iterator()` to `Stream.iterator()`.

## 4. Purpose sections (direct edits, no delta)

- [x] 4.1 `openspec/specs/generic-stream-typing/spec.md` — reword Purpose's
  "Static typing guarantee that the element type flowing through a `Stream`
  pipeline" if it still implies a two-class hierarchy (verify against the
  already-updated wording from the `retire-parallelstream-name` change; no
  edit needed if it already reads correctly for one class).
- [x] 4.2 `openspec/specs/stream-close-handling/spec.md` — reword Purpose's
  "shared by `BaseStream` and `Stream`" to reference `Stream` alone.
- [x] 4.3 `openspec/specs/stream-ordering/spec.md` — reword Purpose's
  "Defines the contract for `BaseStream`'s ordered/unordered bookkeeping"
  and "mirroring Java's `BaseStream.unordered()`" — keep the Java-name
  reference (it names Java's class, not this library's), reword only the
  first mention that describes this library's class.
- [x] 4.4 `openspec/specs/pipeline-composition/spec.md` — reword Purpose's
  "turning a `BaseStream`'s queued chain" to "turning a `Stream`'s queued
  chain".
- [x] 4.5 `openspec/specs/stream-iterator/spec.md` — reword Purpose's
  "Defines the contract for `BaseStream.iterator()`" to "Defines the
  contract for `Stream.iterator()`".

## 5. Documentation

- [x] 5.1 `README.md` — merge the `### BaseStream` API table's rows into the
  `### Stream` table (or otherwise fold the section so there is one table
  documenting one class), preserving every row's content.
- [x] 5.2 `CLAUDE.md` — update the architecture section's `BaseStream`
  references (`self._stream`/`self._chain`/`self._executor`/`self._consumed`
  attribution, and the `on_close()`/`close()` AutoClose paragraph) to
  describe `Stream` directly, and drop the `base_stream.py`/`stream.py`
  two-file framing in favor of the merged `stream.py`.

## 6. Verification

- [x] 6.1 `grep -rn BaseStream openspec/specs/ src/ README.md CLAUDE.md`
  returns no matches, except any deliberately-kept reference to Java's own
  `BaseStream` class (verify each hit by hand rather than requiring zero).
  One hit: `stream-ordering/spec.md`'s "mirroring Java's
  `BaseStream.unordered()`" — the deliberately-kept Java reference per task
  4.3. The other hits, in `src/snakestream.egg-info/PKG-INFO`, are a
  gitignored build artifact regenerated from README.md, not source.
- [x] 6.2 `openspec validate --changes collapse-base-stream-into-stream --strict` passes.
- [x] 6.3 `uv run pytest` — full suite green, with the single
  `test_sequential.py` import-path edit as the only test file change.
- [x] 6.4 `uv run ruff check .` and `uv run ruff format --check .` pass.
- [x] 6.5 `uv run ty check src` passes.
