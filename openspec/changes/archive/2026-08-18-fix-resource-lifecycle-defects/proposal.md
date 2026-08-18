## Why

A review pass surfaced three resource/lifecycle defects that diverge from this API's own stated contracts (Java's AutoClose-style "close everything" semantics, and `StreamBuilder`'s intended build-then-freeze contract): `flat_map()` leaks inner-stream async generators on short-circuit, `close()` stops running handlers after the first one raises, and `StreamBuilder.build()` shares a mutable list with the stream it just built. All three are self-contained, low-risk fixes with no dependents blocking them, making this the top item in the roadmap's **Now** bucket.

## What Changes

- `flat_map()` (`stream.py`): explicitly close the per-outer-element inner generator (`flat_mapper(i).collect(to_generator)`) via `contextlib.aclosing()`, so an early `GeneratorExit` (e.g. from a downstream `.limit()`) doesn't abandon a mid-iteration inner generator without running its cleanup.
- `BaseStream.close()` (`base_stream.py`): run every registered close handler even if an earlier one raises, instead of stopping at the first exception, matching Java's try-with-resources "run every closer, report suppressed exceptions" convention. If one or more handlers raise, `close()` raises after all handlers have run; a single failure raises that exception directly, multiple failures raise the first with the rest attached as `__context__`/suppressed.
- `StreamBuilder.build()` (`stream_builder.py`): snapshot `self._elements` (via `list(self._elements)`) into the `Stream` it constructs, instead of passing the live list by reference, so `add()`/`accept()` calls after `build()` no longer leak into the already-built stream. **BREAKING**: previously, `add()` calls after `build()` were silently visible in the built stream (a latent bug, not a documented/relied-upon feature); after this change they are not.

## Capabilities

### New Capabilities
(none — all three fixes tighten existing, already-specified or implicit contracts rather than introducing new capabilities)

### Modified Capabilities
- `stream-close-handling`: `close()` must invoke every registered handler regardless of earlier handlers raising, and must surface handler exceptions after all handlers have run rather than stopping the sequence.
- `pipeline-composition`: `flat_map()`'s per-outer-element inner stream generator must be explicitly closed on early termination of the outer chain (short-circuit / `GeneratorExit`), not just on normal exhaustion.

A new `stream-builder` capability documents `StreamBuilder`'s existing `add()`/`accept()`/`build()` contract (previously unspecified) including the snapshot-on-build fix.

## Impact

- `src/snakestream/stream.py` (`flat_map()`)
- `src/snakestream/base_stream.py` (`close()`)
- `src/snakestream/stream_builder.py` (`build()`)
- Tests: `tests/test_flat_map.py`, `tests/test_close.py`, and a new `tests/test_stream_builder.py`
- No public API signature changes; `StreamBuilder.build()`'s behavior change is a bug fix tracked as **BREAKING** per `CLAUDE.md`'s migration-log convention (README update required).
