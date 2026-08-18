## 1. close() runs every handler regardless of failures

- [x] 1.1 Rewrite `BaseStream.close()` (`base_stream.py`) to call every handler inside a per-handler `try`/`except Exception`, collecting failures, then raise the first captured exception after the loop (if any)
- [x] 1.2 Add regression tests in `tests/test_close.py`: a raising handler followed by a working handler still runs the second (existing `on_close(bad).on_close(good)` scenario, now asserting `good` was actually called); multiple raising handlers all run and the first exception is raised

## 2. flat_map() closes its inner generator on early termination

- [x] 2.1 Update `Stream.flat_map()` (`stream.py`) to wrap `flat_mapper(i).collect(to_generator)` in `contextlib.aclosing()` around the inner `async for`
- [x] 2.1a (discovered during implementation) Update `collector.py`'s `to_generator()` to wrap its own `composition` in `aclosing()` too, so closing the `flat_map()` wrapper actually cascades to the inner stream's composed generator instead of stopping one layer short
- [x] 2.2 Add a regression test in `tests/test_flat_map.py` using a tracked async generator with `finally:` cleanup, chained with `.flat_map(...).limit(1)`, asserting the cleanup ran after the outer chain short-circuits
- [x] 2.3 Add/verify a test that normal (non-short-circuited) `flat_map()` consumption still yields identical elements as before the fix

## 3. StreamBuilder.build() snapshots its elements

- [x] 3.1 Update `StreamBuilder.build()` (`stream_builder.py`) to pass `list(self._elements)` into `Stream(...)` instead of `self._elements`
- [x] 3.2 Add `tests/test_stream_builder.py`: `add()`/`accept()` accumulate and chain correctly; `build()` captures elements added before it; elements added via `add()` after `build()` do not appear in the already-built stream's output

## 4. Docs and validation

- [x] 4.1 Update README's migration log per `CLAUDE.md` convention, recording `StreamBuilder.build()`'s snapshot behavior change as **BREAKING**
- [x] 4.2 Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`, `uv run ty check src`, and confirm `--cov-fail-under=98` still passes
- [x] 4.3 Move the roadmap.md **Now** #1 item to **Done** with a summary matching the project's existing Done-entry style, referencing this change
