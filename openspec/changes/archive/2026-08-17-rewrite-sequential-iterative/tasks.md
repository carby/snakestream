## 1. Rewrite `_sequential()`

- [x] 1.1 Replace `BaseStream._sequential()`'s recursive, `pop(0)`-based traversal (`base_stream.py:36-49`) with an iterative loop that indexes/iterates `intermediaries` in order, preserving the existing `state_map` per-closure lookup and the exact same return value.
- [x] 1.2 Confirm `_compose()` (`base_stream.py:51-52`) needs no changes — it already passes a fresh list copy (`self._chain[:]`) into `_sequential()`.

## 2. Verify no behavior change

- [x] 2.1 Run the full test suite (`uv run pytest`) and confirm all existing tests, especially `pipeline-composition`-covering tests (chain non-destructiveness, `distinct()`/`limit()`/`skip()` per-composition state reset, `ParallelStream` branch composition), pass unmodified.
- [x] 2.2 Add a regression test asserting `_sequential()` builds a composed pipeline from a long chain of closures without `RecursionError` (isolating the build-time traversal fixed here from per-op async-generator delegation at consumption time, which is a separate, larger redesign tracked as a follow-up change).
- [x] 2.3 Run `uv run ruff check .`, `uv run ruff format --check .`, and `uv run ty check src` to confirm lint/format/type gates pass.
- [x] 2.4 Run `uv run pytest --cov-fail-under=98` to confirm the coverage gate still passes.

## 3. Documentation

- [x] 3.1 Move this roadmap item from `roadmap.md`'s **Now** table to **Done**, following the existing Done-entry format (what changed, why, what was verified), and link to this change's archive location per `CLAUDE.md`'s feature-parity tracking convention.
