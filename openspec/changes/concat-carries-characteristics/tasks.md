## 1. Pin the three defects as failing tests

- [ ] 1.1 Test that `Stream.concat(a.parallel(), b.parallel()).is_parallel()` is `True`, and the one-sided and neither-sided cases; confirm the both-parallel case fails on `main`.
- [ ] 1.2 Test that a concatenation of unordered operands is unordered, for the `a`-only, `b`-only and both cases; confirm they fail.
- [ ] 1.3 Test that consuming an operand after `concat()` raises `IllegalStateException`; confirm that on `main` it instead returns elements and silently shortens the concatenation's output — record the observed `[1,2,3]` / `[4,5]` split in the test's comment, since the wrongness is the point.

## 2. Carry the execution mode

- [ ] 2.1 In `Stream.concat()`, select `RACING` when either operand is parallel and `SEQUENTIAL` otherwise, and set it on the result.
- [ ] 2.2 Test that a later `sequential()` / `parallel()` on the concatenated stream still governs.

## 3. Carry the ordering characteristic

- [ ] 3.1 Seed the concatenated stream's chain with the operation `unordered()` queues when either operand is unordered at the end of its chain, leaving the chain empty when both are ordered.
- [ ] 3.2 Verify the characteristic is derived from the chain, not stored — no new field on `Stream`, and `_is_ordered()` unchanged.
- [ ] 3.3 Test that an order-sensitive operation queued onto an unordered parallel concatenation takes no reorder barrier, following the pattern `racing-encounter-order` establishes for pinning barrier behaviour rather than timing.

## 4. Invalidate the operands

- [ ] 4.1 Mark both operands consumed inside `concat()`, after the existing `_check_not_consumed()` that each `iterator()` call performs, so an already-extended operand still raises with the existing message.
- [ ] 4.2 Leave `iterator()` untouched — confirm `collect(to_generator)` and `flat_map` tests still pass, since `stream-iterator` requires its composition to stay non-destructive.
- [ ] 4.3 Test the same operand passed to two `concat()` calls raises on the second.
- [ ] 4.4 Test the concatenated stream itself remains fully usable and yields `a` then `b`.

## 5. The base-Stream result

- [ ] 5.1 Test that concatenating two instances of one `Stream` subclass yields a base `Stream`, and that concatenating instances of two different subclasses succeeds.
- [ ] 5.2 Add a comment at `concat()` pointing at the spec requirement, so the next reader finds the decision at the code rather than only in `openspec/`.

## 6. Validation

- [ ] 6.1 `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src`.
- [ ] 6.2 `uv run pytest --cov-fail-under=98`.
- [ ] 6.3 `openspec validate concat-carries-characteristics`.
