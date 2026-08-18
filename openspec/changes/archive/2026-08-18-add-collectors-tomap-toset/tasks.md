## 1. `to_map` collector

- [x] 1.1 Add `to_map(key_mapper, value_mapper, merge_function=None)` to `collector.py`: builds a `dict` from `key_mapper(n)`/`value_mapper(n)` per element (both via `_maybe_await`); on a duplicate key, raise `ValueError` when `merge_function is None`, otherwise resolve via `_maybe_await(merge_function, existing, new)`.
- [x] 1.2 Add `tests/test_to_map.py` covering: builds dict from key/value mappers, empty stream → `{}`, async key_mapper/value_mapper awaited, duplicate key with no merge_function raises `ValueError`, duplicate key resolved via merge_function, async merge_function awaited, merge_function never called when no collision occurs.

## 2. `to_set` collector

- [x] 2.1 Add `to_set()` to `collector.py`: builds a `set` from the composed stream's elements, no arguments.
- [x] 2.2 Add `tests/test_to_set.py` covering: builds set from stream elements (including duplicates collapsing), empty stream → `set()`.

## 3. Docs

- [x] 3.1 Add `to_map`, `to_set` rows to README's `Collectors` table.

## 4. Verify

- [x] 4.1 Run `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src` and confirm all pass, including the coverage gate (`uv run pytest --cov-fail-under=98`).
