## Why

`BaseStream` (`base_stream.py`) exists because Java has `BaseStream` as the
shared parent of `Stream`/`IntStream`/`LongStream`/`DoubleStream`. This
library never implemented the primitive-stream specializations — it
deliberately collapsed that distinction already (`summing_int`/`summing_long`
share one body, and the README records why) — and as of the 2026-08-24
`retire-parallelstream-name` change there is no `ParallelStream` either. With
only one concrete subclass left, `Stream(BaseStream[T])`, the two-level split
holds `self._stream`, `self._chain`, `self._executor`, `self._ordered`,
`self._close_handlers` and `self._consumed` on one class and every
intermediate/terminal operation on the other, for no remaining reason to keep
them apart. This is exactly what the roadmap's guiding principle (2026-08-21)
targets: Java structure with no remaining Python reason to exist.

The roadmap flagged this as needing confirmation, not assumption, before
flattening. Confirmed: `BaseStream` is not exported from `__init__.py` (only
`Stream` is public); nothing in `src/` or `tests/` does `isinstance(x,
BaseStream)` or subclasses `BaseStream` directly — the README's documented
subclassing use case (wrapping an I/O-like resource via `on_close()`) already
subclasses `Stream`, which is unaffected; and the one test dependency on the
split, `tests/test_sequential.py`'s `from snakestream.base_stream import
_wrap_sink` (a re-export of `execution.py`'s `_wrap_sink`, not something
`base_stream.py` defines), is a one-line import-path fix, not a behaviour
edit.

## What Changes

- Merge `BaseStream`'s state and methods (`__init__`, `_check_not_consumed`,
  `_derive`, `_compose`, `_evaluate`, `_derive_executor`, `sequential()`,
  `parallel()`, `iterator()`, `unordered()`, `is_ordered()`, `on_close()`,
  `close()`, `is_parallel()`) directly into `Stream` in `stream.py`; delete
  `base_stream.py`.
- `Stream` becomes `Generic[T]` directly (no longer via an intermediate
  base), keeping every existing method's behaviour and signature unchanged.
- Fix `tests/test_sequential.py`'s `_wrap_sink` import to its new location.
- Reword the seven requirements across five capabilities that describe
  `BaseStream` as a class distinct from `Stream`, and the Purpose sections
  that name it (delta cannot touch Purpose, so those are direct edits) —
  same behaviour, current vocabulary, matching the pattern already used for
  the `ParallelStream` retirement.
- Merge README's separate `### BaseStream` API table into the `### Stream`
  table — both already list instance methods of the same runtime class, so
  the split there was always cosmetic.
- Update `CLAUDE.md`'s architecture section, which currently attributes
  `self._stream`/`self._chain`/`self._executor`/`self._consumed` and
  `on_close()`/`close()` to `BaseStream` specifically.

No public API changes: every method `BaseStream` provided is still callable
on `Stream` with the same signature and behaviour; `Stream` is still the sole
export from `snakestream/__init__.py`. Not marked **BREAKING** — the one
`from snakestream.base_stream import ...` import path used internally by a
test is not part of the published surface (`__init__.py` never re-exported
it, and README never documented importing from that module path).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `generic-stream-typing`: "Stream classes are parameterized by element
  type" reworded to describe `Stream` alone (one class, not two) being
  generic over `T`.
- `stream-close-handling`: "on_close() registers a close handler", "close()
  invokes every registered close handler", and "Close handlers propagate
  across sequential()/parallel() mode switches" reworded from
  `BaseStream.on_close()`/`BaseStream.close()`/`(BaseStream)` to `Stream`.
- `stream-ordering`: "BaseStream tracks an ordered/unordered flag defaulting
  to ordered" renamed to "Stream tracks an ordered/unordered flag defaulting
  to ordered"; "BaseStream.unordered() marks the stream as not
  order-dependent" renamed to "unordered() marks the stream as not
  order-dependent"; "The ordering flag survives sequential()/parallel() mode
  switches" reworded to drop `BaseStream.sequential()`/`BaseStream.parallel()`
  in favor of `Stream.sequential()`/`Stream.parallel()`.
- `pipeline-composition`: "Building a composed pipeline does not recurse per
  chained operation" reworded from `BaseStream._compose()` to
  `Stream._compose()`.
- `stream-iterator`: "BaseStream.iterator() exposes the composed pipeline
  without consuming it" renamed to "iterator() exposes the composed pipeline
  without consuming it"; the other two requirements' bodies reworded from
  `BaseStream.iterator()` to `Stream.iterator()`.

## Impact

- `src/snakestream/base_stream.py`: deleted.
- `src/snakestream/stream.py`: gains `BaseStream`'s state and methods;
  becomes the sole class definition for the library's stream type.
- `tests/test_sequential.py`: one import line repointed.
- `openspec/specs/{generic-stream-typing,stream-close-handling,stream-ordering,pipeline-composition,stream-iterator}/spec.md`:
  requirement text updated via delta specs in this change; Purpose sections
  in the same five files edited directly (delta cannot touch Purpose).
- `README.md`: `### BaseStream` table merged into `### Stream`.
- `CLAUDE.md`: architecture section's `BaseStream` references corrected to
  `Stream`.
- No behaviour change anywhere; no test assertion changes beyond the one
  import-path fix.
