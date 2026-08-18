## 1. `grouping_by` collector

- [x] 1.1 Add `grouping_by(classifier, downstream=to_list())` to `collector.py`: buckets elements into `dict[K, list[T]]` via `classifier` (through `_maybe_await`), then runs `downstream` over an async generator rebuilt from each group's list, returning `dict[K, R]`; only keys actually produced by `classifier` appear.
- [x] 1.2 Add a small `_generator_of(items)` helper (or equivalent) in `collector.py` that turns a `list` into an `AsyncGenerator`, for feeding `downstream` collectors — reused by `partitioning_by` too.
- [x] 1.3 Add `tests/test_grouping_by.py` covering: buckets into lists (no downstream), empty stream → `{}`, only-produced-keys present, async classifier awaited, downstream collector composition (e.g. `counting()`, `joining()`), only-present-keys get a downstream-reduced entry.

## 2. `partitioning_by` collector

- [x] 2.1 Add `partitioning_by(predicate, downstream=to_list())` to `collector.py`: splits elements into `True`/`False` buckets via `predicate` (through `_maybe_await`), always both present, then runs `downstream` over each bucket via the shared `_generator_of` helper, returning `dict[bool, R]`.
- [x] 2.2 Add `tests/test_partitioning_by.py` covering: splits into true/false lists (no downstream), empty stream still yields both keys as empty lists, one-empty-partition still appears as a key, async predicate awaited, downstream collector composition (e.g. `counting()`), downstream runs on an empty partition too.

## 3. Docs

- [x] 3.1 Add `grouping_by`, `partitioning_by` rows to README's `Collectors` table.

## 4. Verify

- [x] 4.1 Run `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src` and confirm all pass, including the coverage gate (`uv run pytest --cov-fail-under=98`).
