## 1. `stream.py` core changes

- [x] 1.1 Delete `Stream._compose()`; inline `self._executor.elements(self._chain, self._source)` directly into `Stream.iterator()`'s body, keeping its existing `self._check_not_consumed()` call first.
- [x] 1.2 Change `Stream.collect()`'s `StreamingCollector` branch from `collector(self._compose())` to `collector(self.iterator())`.
- [x] 1.3 Change `_concat()`'s signature to take two `AsyncGenerator`s (`async def _concat(a: AsyncGenerator, b: AsyncGenerator) -> AsyncGenerator`) and drop its `Stream` dependency; its body pulls from `a` then `b` unchanged.
- [x] 1.4 In `Stream.concat()`, call `a.iterator()` and `b.iterator()` before constructing `_concat(...)`, so an already-extended `a` or `b` raises `IllegalStateException` synchronously at the `concat()` call, not on first pull.

## 2. `ops.py` change

- [x] 2.1 In `_FlatMapSink.accept()`, replace `self._flat_mapper(element)._compose()` with `self._flat_mapper(element).iterator()` (still wrapped in `aclosing(...)` exactly as today).

## 3. Spec prose de-staling

- [x] 3.1 In `openspec/specs/pipeline-composition/spec.md`, hand-edited the `## Purpose` section to drop `_compose()` and the already-stale `_parallel()`, restating in the executor vocabulary the rest of the spec already uses. Done during the delta-spec sync step of archiving, alongside the two MODIFIED-requirement merges into the same file.

## 4. Tests

- [x] 4.1 Delete `tests/test_compose.py`; port `test_compose_does_not_shrink_chain` into `tests/test_pipeline_composition.py` (or nearest equivalent) calling `stream.iterator()` instead of `stream._compose()`, and port `test_second_terminal_op_reuses_same_chain` alongside the other chain-reuse coverage in the same file — both already assert exactly what the `pipeline-composition` delta's "Chain length unaffected by composition" scenario now describes in executor-neutral terms.
- [x] 4.2 Add tests for an already-extended stream passed as either argument to `Stream.concat()` raising `IllegalStateException` at the `concat()` call, before any element is pulled from either argument. Placed in `tests/test_pipeline_immutability.py` rather than `tests/test_concat.py` — see 4.5.
- [x] 4.3 Add a test for a merely-*consumed* (never extended) stream passed to `Stream.concat()` not raising, with `concat()`'s output reflecting the existing repeat-terminal-consumption behavior. Placed in `tests/test_pipeline_immutability.py` — see 4.5.
- [x] 4.4 Add a test for a `flat_map()` mapper that returns an already-extended stream raising `IllegalStateException` when the outer chain is consumed. Placed in `tests/test_pipeline_immutability.py` — see 4.5.
- [x] 4.5 Verified `tests/test_pipeline_immutability.py`'s existing scenarios still pass unchanged. That file, not `test_concat.py`/`test_flat_map.py`, is where this project's convention keeps `pipeline-immutability` coverage (it's the dedicated file for the receiver-position checks, parametrized over every intermediate/terminal op), so the three new argument-position scenarios (4.2-4.4) were added there instead of scattered across the two op-specific files.
- [x] 4.6 Run `uv run pytest --cov-fail-under=98` and confirm the coverage gate still passes with `_compose()` removed.

## 5. Verification

- [x] 5.1 `uv run ruff check .` and `uv run ruff format --check .`.
- [x] 5.2 `uv run ty check src`.
- [x] 5.3 `openspec validate --strict collapse-compose-into-iterator` passes with all four artifacts present.
