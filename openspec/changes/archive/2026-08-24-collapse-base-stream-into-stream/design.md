## Context

`base_stream.py` (128 lines) defines `BaseStream(Generic[T])`, holding
`self._stream`, `self._chain`, `self._close_handlers`, `self._ordered`,
`self._consumed`, `self._executor`, and the methods `_check_not_consumed`,
`_derive`, `_compose`, `_evaluate`, `_derive_executor`, `sequential()`,
`parallel()`, `iterator()`, `unordered()`, `is_ordered()`, `on_close()`,
`close()`, `is_parallel()`. `stream.py` (219 lines) defines `class
Stream(BaseStream[T])`, the sole subclass, adding every intermediate op
(`filter`, `map`, `flat_map`, `sorted`, `distinct`, `peek`, `limit`, `skip`)
and terminal op (`collect`, `reduce`, `for_each`, `for_each_ordered`,
`to_array`, `find_first`, `find_any`, `max`/`min`, `*_match`, `count`) plus
its static factories (`of`, `empty`, `concat`, `builder`, `iterate`).
`base_stream.py` is imported from exactly one other file in `src/`
(`stream.py`) and one file in `tests/` (`test_sequential.py`, for a
re-exported `_wrap_sink`). See proposal.md for the full confirmation that
nothing else depends on the split.

## Goals / Non-Goals

**Goals:**
- One class, `Stream`, carrying everything `BaseStream` + `Stream` carried
  today, with identical public behaviour and signatures.
- Delete `base_stream.py` outright — no re-export shim, no deprecated alias,
  matching this project's established pre-1.0 clean-break convention.

**Non-Goals:**
- No change to `Op`/`Sink`/`Executor` protocols, `execution.py`, `ops.py`,
  `terminals.py`, `sink.py`, or `callable_dispatch.py` — this change touches
  only where the stream state and its own methods live, not how the chain
  executes.
- No change to `Stream`'s public method signatures, return types, or
  behaviour. `_derive()`/`_derive_executor()` already build the new instance
  via `type(self)(...)`, which continues to work unchanged once there is
  only one class in the hierarchy.
- No rename of `stream.py` or restructuring of its internal method order
  beyond inserting the merged block.

## Decisions

**Merge into `stream.py`, not the reverse.** `stream.py` is the file that
survives (it already holds the public factory methods and the bulk of the
public surface); `base_stream.py` is deleted rather than becoming the
merged file, so the module a reader opens for `Stream` is the one importing
from `snakestream import Stream` resolves to today (`stream.py`, per
`__init__.py`).

**Class body order: state and lifecycle first, then the merged instance
methods, then the existing `Stream`-only methods in their current order.**
`__init__`, `_check_not_consumed`, `_derive`, `_compose`, `_evaluate`,
`_derive_executor` are the private machinery every other method calls
through, so they lead; `sequential()`/`parallel()`/`iterator()`/
`unordered()`/`is_ordered()`/`on_close()`/`close()`/`is_parallel()` follow,
preserving their relative order from `base_stream.py`; the static factories
and the existing intermediate/terminal methods keep their current position
and order in the file, unmoved, since they are exactly where a reader
already expects them.

**No compatibility shim for `from snakestream.base_stream import
BaseStream`.** Considered and rejected for the same reason the
`ParallelStream` retirement and the `concat()`/`__await__` and `to_list`
factory changes rejected shims: `base_stream.py` is not exported from
`__init__.py`, so keeping a hollow module around to catch a theoretical
internal import would preserve a path nothing in this codebase or its
README ever documented as public, at the cost of a permanently-confusing
extra file. The only real caller, `test_sequential.py`, gets a one-line
import-path fix as part of this change instead.

**Spec deltas reword `BaseStream` requirement text to `Stream` in place,
not RENAMED + MODIFIED.** Three of the seven requirements also change
title (`stream-ordering`'s two `BaseStream.*`-prefixed titles,
`stream-iterator`'s `BaseStream.iterator() exposes...`); OpenSpec's
`RENAMED` operation is for name-only changes, and these also reword body
text. Following the precedent set by `retire-parallelstream-name` (which
renamed `for_each_ordered() preserves encounter order on ParallelStream` to
its `RACING`-worded title inside one `MODIFIED` block, not a separate
`RENAMED` entry), this change does the same: rename and reword together
inside `MODIFIED Requirements`, applied directly to the main specs during
apply exactly as the prior change did.

## Risks / Trade-offs

**[Risk] A merge is a bigger, harder-to-scan diff than a typical
behaviour-neutral cleanup, raising the odds of an incidental behaviour
change slipping in unnoticed.** → Mitigation: the merge is a cut-and-paste
of `base_stream.py`'s methods into `stream.py`, verified byte-identical
(modulo the `BaseStream` → `Stream` class line and merged import block) by
diffing the moved block against `git show HEAD:src/snakestream/base_stream.py`
before deleting the source file — the same verification method the
`ops.py` split used when it moved code the other direction. The "green with
no test file edited" tripwire applies except for the one `test_sequential.py`
import line, called out explicitly in the proposal so it isn't mistaken for
a missed regression.

**[Risk] `Generic[T]` inheritance changes shape** — `Stream` currently gets
`Generic[T]` transitively through `BaseStream(Generic[T])`; after the merge
`Stream` must declare `Generic[T]` itself. → Mitigation: `class
Stream(Generic[T]):` is a mechanical one-line change; `uv run ty check src`
is in the task list specifically to catch any typing regression this could
cause (e.g. if some other file's type checking relied on the two-level
`isinstance`/`issubclass` shape, which the earlier grep found nothing does).

**[Risk] `type(self)(self._stream, self._close_handlers)` in `_derive()`/
`_derive_executor()` assumes a one-argument-plus-close-handlers
constructor signature.** → Mitigation: unaffected by this change —
`Stream.__init__` keeps exactly the signature `BaseStream.__init__` had
(`source`, `close_handlers`), so `type(self)(...)` continues to resolve to
`Stream` and construct correctly, whether `Stream` itself is subclassed (the
documented use case) or not.
