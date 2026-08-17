## 1. `min_by`/`max_by` collectors

- [x] 1.1 Add `min_by(comparator)`/`max_by(comparator)` to `collector.py`: private shared extremum-loop helper plus two thin public factories, reusing `check_comparator_result_type` from `sort.py` and `_maybe_await` for comparator dispatch — mirroring `Stream._min_max`'s logic (tie-break, `TypeError` guard, `None` on empty stream).
- [x] 1.2 Add `tests/test_min_by.py`/`tests/test_max_by.py` covering: smallest/largest selection, empty stream → `None`, tie-break keeps first, async comparator, `TypeError` on bool-returning comparator.

## 2. `reducing` collectors

- [x] 2.1 Add `reducing(...)` to `collector.py`: `@overload` signatures for the 1-arg (`binary_operator`), 2-arg (`identity, binary_operator`), and 3-arg (`identity, mapper, binary_operator`) forms, one runtime body dispatching via a `_UNSET` sentinel (mirroring `Stream.reduce`), using `_maybe_await` for mapper/operator dispatch.
- [x] 2.2 Add `tests/test_reducing.py` covering: no-identity fold (empty → `None`, single-element short-circuit, multi-element fold order), identity fold (empty → identity unchanged, multi-element), mapper form (maps then folds, empty → identity unchanged), async mapper/operator awaiting, and overload dispatch by arg count.

## 3. Docs

- [x] 3.1 Add `min_by`, `max_by`, `reducing` rows to README's `Collectors` table.

## 4. Verify

- [x] 4.1 Run `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src` and confirm all pass, including the coverage gate (`uv run pytest --cov-fail-under=98`).
