## 1. Create `ops.py`

- [x] 1.1 Create `src/snakestream/ops.py` with the `from __future__ import annotations` header and the imports the moved code needs: `aclosing` (contextlib), `isawaitable` (inspect), `Any`/`cast` (typing), `Awaitable` (collections.abc), `is_async_callable` (callable_dispatch), `Counter`/`IntermediateSink`/`Op`/`Sink`/`StatefulOp`/`StatefulSink`/`StatelessOp` (sink), `merge_sort` (sort), and `Comparator`/`Consumer`/`FlatMapper`/`Mapper`/`Predicate`/`T` (type).
- [x] 1.2 Move the eight op/sink pairs from `stream.py` (currently lines 44–223) into `ops.py` verbatim, keeping their existing order: `_FilterSink`/`_FilterOp`, `_MapSink`/`_MapOp`, `_PeekSink`/`_PeekOp`, `_SortedSink`/`_SortedOp`, `_FlatMapSink`/`_FlatMapOp`, `_DistinctSink`/`_DistinctOp`, `_LimitSink`/`_LimitOp`, `_SkipSink`/`_SkipOp`. Do not edit a class body — including `_SortedSink.end()`'s merge_sort comment.
- [x] 1.3 Confirm `ops.py` imports nothing from `snakestream.stream` at runtime; if a `Stream` name is needed for annotations only, use a `TYPE_CHECKING` guard.

## 2. Update `stream.py`

- [x] 2.1 Delete the moved block from `stream.py` and add `from snakestream.ops import _DistinctOp, _FilterOp, _FlatMapOp, _LimitOp, _MapOp, _PeekOp, _SkipOp, _SortedOp`.
- [x] 2.2 Remove imports `stream.py` no longer uses after the cut (candidates: `aclosing`, `merge_sort`, and the `sink` imports `Counter`/`IntermediateSink`/`Op`/`Sink`/`StatefulOp`/`StatefulSink`/`StatelessOp`), keeping anything the `Stream` API still needs (e.g. `check_comparator_result_type`, `is_async_callable`, `isawaitable`).
- [x] 2.3 Verify `PROCESSES`, `_UNSET`, `_concat`, and the `TYPE_CHECKING`-guarded `StreamBuilder` import all stayed in `stream.py`.

## 3. Update tests

- [x] 3.1 Change `tests/test_op_protocol.py`'s import of the eight op classes from `snakestream.stream` to `snakestream.ops`, leaving its `Stream` import on `snakestream.stream`.
- [x] 3.2 Grep `src/` and `tests/` for any other reference to the moved names and update it; confirm `tests/test_sequential.py` and `tests/test_sink.py` need no change.

## 4. Validate

- [x] 4.1 `uv run pytest` — full suite green, coverage at or above the pre-change figure (the gate is 98%).
- [x] 4.2 `uv run ruff check .` and `uv run ruff format --check .` — clean, in particular no unused-import findings in `stream.py`.
- [x] 4.3 `uv run ty check src` — clean.
- [x] 4.4 Confirm `git diff --stat` shows only `src/snakestream/stream.py`, `src/snakestream/ops.py`, and `tests/test_op_protocol.py`, and that the net line change is approximately zero plus the new module's import header.

## 5. Record

- [x] 5.1 Move the `ops.py` split item from **Now** to **Done** in `roadmap.md`, noting the resulting `stream.py` line count and that no spec or README edit was needed.
- [x] 5.2 Confirm README needs no edit (every moved name is private and unexported) and state that explicitly in the Done entry.
