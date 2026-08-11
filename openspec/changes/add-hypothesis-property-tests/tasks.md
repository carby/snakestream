## 1. Setup

- [x] 1.1 Add `hypothesis` to the `dev` dependency group in `pyproject.toml` and run `uv sync`.

## 2. `map` property tests

- [x] 2.1 Add a `@given`-decorated test in `tests/test_map.py` asserting `Stream.of(values).map(mapper).collect(to_list)` equals `list(map(mapper, values))` for generated `values` (including empty/single-element lists).
- [x] 2.2 Add a variant using an `async def` mapper, asserting the same equivalence.

## 3. `filter` property tests

- [x] 3.1 Add a `@given`-decorated test in `tests/test_filter.py` asserting `Stream.of(values).filter(predicate).collect(to_list)` equals `list(filter(predicate, values))` for generated `values` (including empty/single-element lists).
- [x] 3.2 Add a variant using an `async def` predicate, asserting the same equivalence.

## 4. `reduce` property tests

- [x] 4.1 Add a `@given`-decorated test in `tests/test_reduce.py` asserting `Stream.of(values).reduce(identity, accumulator)` equals `functools.reduce(accumulator, values, identity)` for generated `values` and a fixed identity (including empty/single-element lists).
- [x] 4.2 Add a variant using an `async def` accumulator, asserting the same equivalence.

## 5. `sorted` property tests

- [x] 5.1 Confirm the current `Comparator` contract in `stream.py` (3-way int comparator, first-of-equal-elements order preserved per the recent bugfix noted in `roadmap.md`'s Done section) before writing the oracle.
- [x] 5.2 Add a `@given`-decorated test in `tests/test_sorted.py` asserting `Stream.of(values).sorted().collect(to_list)` is a permutation of `values`, non-decreasing, and stable, matching `sorted(values)` for default ordering (including empty/single-element lists).
- [x] 5.3 Add a `@given`-decorated test with an explicit `Comparator` (sync), asserting equivalence with `sorted(values, key=...)` or an equivalent reference using `functools.cmp_to_key`.
- [x] 5.4 Add a variant using an `async def` comparator, asserting the same equivalence.

## 6. `distinct` property tests

- [x] 6.1 Confirm `distinct()`'s dedup mechanism (hash-based or otherwise) in `stream.py` before writing the oracle, and restrict generated elements to hashable types accordingly.
- [x] 6.2 Add a `@given`-decorated test in `tests/test_distinct.py` asserting `Stream.of(values).distinct().collect(to_list)` has no duplicates and preserves first-seen order, matching a dict-based dedup reference (including empty/single-element lists).

## 7. Verification

- [x] 7.1 Run `uv run pytest` and confirm all new property tests pass alongside existing tests.
- [x] 7.2 Run `uv run pytest --cov-fail-under=98` and confirm the coverage gate still passes.
- [x] 7.3 Run `uv run ruff check .` and `uv run ruff format --check .` on the new/modified test files.
