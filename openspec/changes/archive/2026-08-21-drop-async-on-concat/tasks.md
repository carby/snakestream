## 1. Change the signature

- [x] 1.1 In `src/snakestream/stream.py`, change the `concat` staticmethod from `async def concat(a: Stream[T], b: Stream[T]) -> Stream[T]` to `def concat(a: Stream[T], b: Stream[T]) -> Stream[T]`, leaving the body (`Stream(_concat(a, b))`) and `_concat` itself untouched.
- [x] 1.2 Confirm by reading that no other call site in `src/` uses `Stream.concat` (`grep -rn "concat" src/`), so `_concat`, the generator bridge, and `_consumed` bookkeeping all stay as they are.

## 2. Update the in-repo call sites

- [x] 2.1 In `tests/test_concat.py`, drop the `await` from both call sites: `(await Stream.concat(a, b)).collect(to_generator)` becomes `Stream.concat(a, b).collect(to_generator)` in `test_concat_simple` and `test_concat_with_intermediaries`.
- [x] 2.2 Run `uv run pytest tests/test_concat.py` and confirm both tests pass against the new signature.

## 3. Cover the new spec requirements with tests

- [x] 3.1 Add a test asserting `Stream.concat(a, b)` returns a `Stream` instance directly (not a coroutine) — e.g. `isinstance(Stream.concat(a, b), Stream)` — covering "Concatenating without await".
- [x] 3.2 Add a test asserting `await Stream.concat(a, b)` raises `TypeError`, covering "Awaiting the result is an error".
- [x] 3.3 Add a test that calls `Stream.concat(a, b)` from a plain synchronous function (no `async def`, no running loop) and asserts a `Stream` comes back, covering "Callable outside a coroutine".
- [x] 3.4 Add a test for an empty input on either side (`Stream.empty()` as `a`, then as `b`), asserting the result is exactly the other stream's elements in order, covering "Empty input on either side".
- [x] 3.5 Add laziness tests: (a) construct `Stream.concat(a, b)` where both inputs carry a `peek` recording into a list, never consume the result, and assert the list is empty; (b) consume only as far as the first stream's elements and assert the second stream's `peek` recorded nothing. Covers both laziness scenarios.
- [x] 3.6 Run `uv run pytest tests/test_concat.py` and confirm all new tests pass.

## 4. Document the break

- [x] 4.1 Add a `**0.3.5 -> next:**` entry to README's `## Migration` list stating that `Stream.concat(a, b)` is no longer a coroutine function, that callers must drop the `await`, and that an unmigrated `await Stream.concat(a, b)` raises `TypeError: object Stream can't be used in 'await' expression`. Reference `openspec/changes/drop-async-on-concat`, matching the neighbouring entries' style.
- [x] 4.2 Verify README's API table row for `concat` (line ~109) still reads correctly — it already documents the return type as `Stream`, so expect no edit; note explicitly if that turns out to be wrong.
- [x] 4.3 Check the rest of README (and any docstrings) for `await Stream.concat` examples and update any found.

## 5. Gates

- [x] 5.1 `uv run pytest` — full suite green.
- [x] 5.2 `uv run ruff check .` and `uv run ruff format --check .` clean.
- [x] 5.3 `uv run ty check src` clean.
- [x] 5.4 `uv run pytest --cov-fail-under=98` passes.
- [x] 5.5 `openspec validate drop-async-on-concat --strict` passes.
