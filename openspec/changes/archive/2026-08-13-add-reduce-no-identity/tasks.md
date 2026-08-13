## 1. Type alias

- [x] 1.1 Add a `BinaryOperator` (or similarly Java-parity-named) alias to `type.py` for the no-identity accumulator shape (`T, T -> T`, sync or async), following the existing `Predicate`/`Mapper`/`Accumulator` pattern.

## 2. Implementation

- [x] 2.1 Add an `@overload` signature to `stream.py`'s `reduce()` for the identity form (`identity: T | R, accumulator: Accumulator[T, R]) -> T | R`), matching current behavior.
- [x] 2.2 Add an `@overload` signature for the no-identity form (`accumulator: BinaryOperator[T]) -> T | None`).
- [x] 2.3 Implement the runtime branch: default `identity` to a private `_UNSET` sentinel; when unset, pull the first element from `self._compose()` as the seed (returning `None` immediately if the source is empty) before folding the rest through the existing accumulator-dispatch loop via `_maybe_await`.
- [x] 2.4 Verify the single-element case returns that element without ever calling `accumulator` (falls out naturally once the first-element-as-seed loop has nothing left to fold).

## 3. Tests

- [x] 3.1 Add tests for `Stream.reduce(accumulator)`: empty stream returns `None` and never calls the accumulator; single-element stream returns that element without calling the accumulator; multi-element stream folds left in order.
- [x] 3.2 Add a test with an async accumulator, asserting the result is awaited (not a coroutine) and each intermediate call is awaited before use.
- [x] 3.3 Add a regression test confirming the existing `Stream.reduce(identity, accumulator)` 2-arg call shape is unchanged (same result as before this change on a representative case).
- [x] 3.4 Run `uv run pytest tests/test_reduce.py` (or new test file) and `uv run pytest --cov-fail-under=98` to confirm coverage.

## 4. Type checking and lint

- [x] 4.1 Run `uv run ty check src` and fix any type errors surfaced by the new `@overload` signatures or `BinaryOperator` alias.
- [x] 4.2 Run `uv run ruff check .` and `uv run ruff format --check .`.

## 5. Docs

- [x] 5.1 Update `README.md`'s Java Stream API parity tracking to mark `reduce(BinaryOperator)` as implemented.
