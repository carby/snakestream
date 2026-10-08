+++
id = "resource-lifecycle-defects"
title = "Fixed three resource/lifecycle defects found in review"
filed = 2026-08-18
closed = 2026-08-18
outcome = "shipped"
+++

Fixed three resource/lifecycle defects found in review: (a) `flat_map()`
(`stream.py`) leaked the current inner stream's async generator when the
outer chain short-circuited (e.g. a downstream `.limit()`) — each outer
element's fresh `flat_mapper(i).collect(to_generator)` generator was only
ever exhausted, never explicitly `.aclose()`'d, so an early `GeneratorExit`
on the outer chain abandoned whatever inner generator was mid-iteration.
Fixed by wrapping that inner generator in `contextlib.aclosing()`
(`stream.py`). Discovered during implementation: `aclosing()` alone wasn't
sufficient — `collect(to_generator)` returns a second-layer wrapper
generator (`collector.py`'s `to_generator()`) whose `async for n in
composition: yield n` body didn't propagate `.aclose()` to `composition`
either, confirmed with a minimal repro showing a plain `async for` never
auto-closes what it iterates. Fixed `to_generator()` to also wrap
`composition` in `aclosing()`, guarded by `hasattr(composition, "aclose")`
since `to_generator()` also accepts plain `AsyncIterable`/`AsyncIterator`
objects without an `aclose` method (e.g. a custom `__anext__`-only
iterator, already covered by `tests/test_of.py::test_input_async_iterator`).
This closes the gap only as deep as `flat_map()`'s stated repro case (a
single-level inner stream); N-layers-deep propagation across every op in
`stream.py` remains out of scope, tracked under the **Next**-bucket
Sink-chain redesign item. (b) `BaseStream.close()` (`base_stream.py`)
iterated `_close_handlers` with a plain `for` loop and no `try`/`except`,
so a raising handler stopped every handler after it from running, unlike
Java's try-with-resources convention of running every closer regardless.
Fixed by calling every handler inside a per-handler `try`/`except
Exception`, collecting failures, then raising the first captured exception
once every handler has run (not an `ExceptionGroup`, since this project's
CI matrix still targets Python 3.10). (c) `StreamBuilder.build()`
(`stream_builder.py`) passed `self._elements` into `Stream(...)` by
reference rather than snapshotting it, so `add()`/`accept()` calls made
*after* `build()` leaked into the already-built stream. Fixed by
snapshotting via `list(self._elements)`. Added regression tests in
`tests/test_close.py`, `tests/test_flat_map.py`, and a new
`tests/test_stream_builder.py`. Added a new `stream-builder` spec
capturing `StreamBuilder`'s previously-undocumented `add()`/`accept()`/
`build()` contract, and extended `stream-close-handling` and
`pipeline-composition` for the `close()`/`flat_map()` fixes. Updated
README's migration log: `StreamBuilder.build()`'s snapshot behavior is
tracked as **BREAKING** per `CLAUDE.md`'s convention (relying on
post-build mutation leaking into a built stream was never a documented
feature). See `openspec/changes/fix-resource-lifecycle-defects`.
