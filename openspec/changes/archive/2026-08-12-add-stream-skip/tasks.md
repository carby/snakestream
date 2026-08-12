## 1. Implementation

- [x] 1.1 Add `_SkipOp` class to `src/snakestream/stream.py` (alongside
      `_LimitOp`/`_DistinctOp`): `make_state() -> list[int]` returning a
      1-element counter, `async def __call__(iterable, state=None)` that
      drains and discards elements while the counter is below `n`
      (incrementing per drained element), then yields the rest.
- [x] 1.2 Add `Stream.skip(n: int) -> Stream[T]` method that appends a
      `_SkipOp(n)` to `self._chain` and returns `self`, placed near
      `limit()`.

## 2. Tests

- [x] 2.1 Add `tests/test_skip.py` covering: dropping first n of a longer
      source, source shorter than n yields nothing, `skip(0)` is a no-op,
      async and sync sources.
- [x] 2.2 Add regression coverage (in `test_skip.py` or
      `tests/test_pipeline_composition.py` if that's where existing
      `limit()`/`distinct()` reset tests live) for: sequential `skip()`
      state resets across separate compositions of the same chain; parallel
      `skip()` drops exactly `n` total across racing `ParallelStream`
      branches, not per-branch; parallel `skip()` shared state resets across
      compositions.
- [x] 2.3 Run `uv run pytest --cov-fail-under=98` and confirm the new code
      is covered.

## 3. Docs

- [x] 3.1 Update README.md's Java `Stream` API parity table to mark
      `skip(n)` as implemented.
- [x] 3.2 Move the `Stream.skip(n)` line from roadmap.md's Now table to
      Done, with a summary of what was implemented (per the existing Done
      entries' format).

## 4. Validation

- [x] 4.1 `uv run ruff check .` and `uv run ruff format --check .`
- [x] 4.2 `uv run ty check src`
