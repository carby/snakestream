+++
id = "collapse-base-stream-into-stream"
title = "Collapsed `BaseStream` into `Stream`; `base_stream.py` is gone"
filed = 2026-08-24
closed = 2026-08-24
outcome = "shipped"
+++

**Collapsed `BaseStream` into `Stream`; `base_stream.py` is gone**
(2026-08-24). The split existed because Java needs `BaseStream` as the shared
parent of `Stream`/`IntStream`/`LongStream`/`DoubleStream`. This library never
implemented the primitive specializations, and after the `ParallelStream`
retirement below there was exactly one concrete subclass left — so the
two-level tree held state on one class and operations on the other for no
remaining reason. Exactly what the guiding principle targets: Java structure
with no remaining Python reason to exist.

**The roadmap entry demanded confirmation rather than assumption, and got
it.** `BaseStream` was never exported from `__init__.py`; nothing in `src/` or
`tests/` did `isinstance(x, BaseStream)` or subclassed it directly — the
README's documented subclassing use case (wrapping an I/O-like resource via
`on_close()`) already subclasses `Stream`; and the one test dependency on the
split, `tests/test_sequential.py`'s `from snakestream.base_stream import
_wrap_sink`, turned out to be importing a re-export of `execution.py`'s
`_wrap_sink` rather than anything `base_stream.py` defined — a one-line
import-path fix, not a behaviour edit.

`Stream` is now `Generic[T]` directly, with every merged method keeping its
signature and behaviour. README's separate `### BaseStream` API table was
merged into `### Stream` (both always listed instance methods of the same
runtime class), and `CLAUDE.md`'s architecture section, which attributed
`self._stream`/`self._chain`/`self._executor`/`self._consumed` and the
AutoClose pair to `BaseStream`, now describes `Stream`. Full suite green with
that single import-path edit as the only test change; `ruff`, `ty` and
`openspec validate --strict` all pass. The one surviving `BaseStream`
reference in `openspec/specs/` is deliberate: `stream-ordering`'s Purpose
cites *Java's* `BaseStream.unordered()` as the mirrored API. See
`openspec/changes/archive/2026-08-24-collapse-base-stream-into-stream`.

**Opened the 2026-08-24 legibility batch** now sitting at **Now** items 2-8:
with the state and the operations finally in one file, reading `stream.py`
end-to-end surfaced the three-drive-sites/one-docstring mismatch, the
duplicated derive bodies and the `_stream`-vs-`source` naming split.
