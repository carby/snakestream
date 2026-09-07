## 1. Baseline

- [x] 1.1 Capture the pre-change baseline on the `collapse-terminal-collector-duplication` harness (20,000 elements, interleaved round-robin, best of 3, median of 25 rounds, ns/element) for the four shapes design.md quotes — key segment, comparator segment, two-segment chain, and async extractor with one key segment — and record the numbers so task 4.1 has something to compare against.
- [x] 1.2 Write a throwaway equivalence harness that evaluates 10 comparator shapes (bare key segment, comparator segment, bare comparator segment, two- and three-segment chains, `reversed()` before and after `then_comparing()`, `nulls_first()`, `nulls_last()`, `nulls_first(None)`) against 25 input pairs covering `None` on either or both sides, and verify it passes against unmodified `comparator.py` — capture its output as the reference the post-change run must match exactly.

## 2. Merge the four sign functions into two

- [x] 2.1 Replace `_key_segment_sign_sync` and `_comparator_segment_sign_sync` (`src/snakestream/comparator.py`) with one `_segment_sign_sync(extractor, comparator, a, b, nulls)`: `extractor is None` means compare the elements themselves, `comparator is None` selects natural ordering and returns `(ea > eb) - (ea < eb)` **before** the `type(sign) is not int` guard, per design.md Decision 3. Verify `uv run pytest tests/test_comparator.py tests/test_sorted.py tests/test_min_max.py` passes.
- [x] 2.2 Replace `_key_segment_sign_async` and `_comparator_segment_sign_async` with one `async _segment_sign_async(extractor, comparator, a, b, nulls, is_async)`, awaiting the extractor only when `is_async`, never awaiting the comparator (always sync per Decision 2/3). Verify the same three test files pass.
- [x] 2.3 Update both merged docstrings so they carry forward what the four they replace explained: the both-`None` tie folding into the caller's `sign == 0` continue, the bare-comparator segment shape, and why natural ordering never reaches the contract check. Verify `uv run ruff check .` and `uv run ruff format --check .` pass.

## 3. Normalise the segment list once per composition

- [x] 3.1 In `KeyComparator.__init__`, build `self._norm` as a tuple of `(extractor, comparator_or_None, descending, is_async)` per segment, unpacking `isinstance(payload, tuple)` once here; demote `_is_async` to a local used only to compute `_any_async` (Decision 4). Verify `.segments` is byte-for-byte unchanged in shape by running `uv run pytest tests/test_sorted.py`, which exercises `sort.py`'s `_segment_column()` fast path.
- [x] 3.2 Rewrite `_compare_sync` and `_compare_async` to iterate `self._norm` directly, so no `isinstance()` and no `zip(..., strict=True)` runs per comparison. Verify `uv run pytest` passes in full.
- [x] 3.3 Extend the `KeyComparator` class docstring's existing "once here at construction rather than per element or per comparison" sentence to cover `_norm`, and state that `.segments` remains the shape `sort.py` reads. Verify `uv run ruff format --check .` and `uv run ty check src` pass.

## 4. Verify

- [x] 4.1 Re-run the task 1.1 benchmark and confirm the gate: no shape regresses past +10% ns/element, with the async key-segment shape expected around −20%. Record the figures in the change directory so the roadmap entry can cite them.
- [x] 4.2 Re-run the task 1.2 equivalence harness against the merged implementation and confirm output is identical to the task 1.2 reference across all 10 shapes × 25 pairs, then delete the harness.
- [x] 4.3 Run the full gate — `uv run pytest --cov-fail-under=98`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src` — and confirm no test needed editing (no test names any of the four removed functions; verified by grep over `tests/`).
- [x] 4.4 Confirm `src/snakestream/sort.py` is untouched in the diff and no README Migration entry is owed (no exported surface changed), per the proposal's Impact and design.md's Migration Plan.
