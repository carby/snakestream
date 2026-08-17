## 1. Implementation

- [x] 1.1 Add `Stream.for_each_ordered(consumer)` in `src/snakestream/stream.py`, driving consumption via `self._sequential(self._chain[:], self._stream)` rather than `self._compose()`, dispatching the consumer through the existing `_maybe_await` helper (same as `for_each()`).

## 2. Tests

- [x] 2.1 Add `tests/test_for_each_ordered.py` covering: sequential `Stream` preserves source order, sync and async consumers both work, `ParallelStream` preserves encounter order via `for_each_ordered()`, and a sanity check that plain `for_each()` on `ParallelStream` is unaffected (still exercised, not asserted-unordered, since order is nondeterministic).
- [x] 2.2 Run `uv run pytest` and confirm the coverage gate (`--cov-fail-under=98`) still passes.

## 3. Docs

- [x] 3.1 Update README.md's Java Stream API parity tracking to mark `forEachOrdered` as implemented, per `CLAUDE.md`.
- [x] 3.2 Move this item from roadmap.md's **Now** table to **Done**, following the existing Done-entry format (what/why/how, referencing `openspec/changes/add-stream-foreach-ordered`).
