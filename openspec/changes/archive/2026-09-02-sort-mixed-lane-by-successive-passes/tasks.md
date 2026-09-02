## 1. Establish the baseline

- [x] 1.1 Write the benchmark harness before touching `sort.py`: current lanes vs. successive passes over the same columns, asserting element-identical output (tie order included) at single / uniform / mixed shapes and k in 1..8, and verify it reproduces design.md's table on this machine
- [x] 1.2 Record the pre-change `sort.py` statement and branch counts from `uv run pytest --cov`, so the post-change reading can be compared rather than merely taken

## 2. Rewrite the lane block

- [x] 2.1 Replace the three-lane `(rows, reverse)` derivation in `_sort_by_key()` with the successive-pass loop of design.md Decision 1 — first pass a `sorted()` on the least significant column, remaining passes `.sort()` in decreasing significance — and verify `uv run pytest tests/test_comparator_segments.py tests/test_comparing.py tests/test_nulls_ordering.py tests/test_sorted.py` is green
- [x] 2.2 Switch the undecorate to `list(map(itemgetter(-1), paired))` per Decision 4 and verify the same four test files stay green
- [x] 2.3 Delete the `_Descending` class and verify `grep -rn "_Descending" src tests` returns nothing
- [x] 2.4 Confirm the `len(segments) == 1` fan-out branch is untouched and that a single-segment chain still reaches exactly one `sorted()` call, by reading the shipped code against Non-Goals

## 3. Prove the behaviour the spec now claims

- [x] 3.1 Add the delta spec's third scenario as a test — a two-segment chain whose first segment yields a distinct key per element and whose second yields mutually incomparable keys — and verify it raises `TypeError` where it did not before
- [x] 3.2 Verify the two pre-existing scenarios in "Keys within a segment must be mutually comparable" still hold unchanged
- [x] 3.3 Verify stability across all three shapes: elements the whole chain treats as equivalent come back in encounter order, single / uniform / mixed alike (`comparator-contract`'s "sorted() is stable")
- [x] 3.4 Verify a null-tolerant chain still places `None` at the declared end under mixed directions, and that `reversed()` on a mixed chain still equals negation of the whole ordering

## 4. Re-measure and rewrite what the docstrings claim

- [x] 4.1 Re-run 1.1's harness against the shipped code and record the figures
- [x] 4.2 Rewrite `_sort_by_key()`'s docstring: the three-lane description and the ~3.3x mixed-lane figure describe a structure that no longer exists; state the successive-pass rule, the CPython stability guarantee it rests on, and the measured uniform crossover between four and five segments
- [x] 4.3 Check `sort()`'s docstring and `_segment_column()`'s reference to "`_Descending`/`reverse=True`/plain tuple order" for claims the rewrite invalidates, and correct them
- [x] 4.4 Update design.md's Risks table with the shipped figures if they differ materially from the exploration's

## 5. Gate

- [x] 5.1 `uv run pytest` green, and the test count is the pre-change count plus exactly the tests added in section 3
- [x] 5.2 `uv run ruff check .`, `uv run ruff format --check .` and `uv run ty check src` clean
- [x] 5.3 `uv run pytest --cov-fail-under=98` passes, and compare `sort.py`'s statement/branch counts against 1.2 — every removed branch must have been covered before, so that no arm has gone silently unreachable
- [x] 5.4 Confirm `git diff --stat tests/` shows only the additions from section 3 — no existing test file, name or import touched — and that no README migration-log entry is owed, since nothing a caller can name has moved
