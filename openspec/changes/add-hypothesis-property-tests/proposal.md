## Why

Hand-written unit tests for `map`, `filter`, `reduce`, `sorted`, and `distinct` only cover the specific inputs their authors thought of. Property-based testing with `hypothesis` cheaply generates edge cases those tests miss — empty streams, single-element streams, duplicate keys, non-comparable types — for the cost of stating the invariant once per operation. This is the top item in `roadmap.md`'s **Now** section: low-risk, self-contained, and requires no API changes.

## What Changes

- Add `hypothesis` to the `dev` dependency group in `pyproject.toml`.
- Add property-based tests (new `test_*_hypothesis.py` files, or `@given`-decorated tests added to the existing `test_map.py`, `test_filter.py`, `test_reduce.py`, `test_sorted.py`, `test_distinct.py`) asserting invariants for each of the five operations, e.g.:
  - `map`: output length equals input length; each output element equals the mapper applied to the corresponding input element.
  - `filter`: every output element satisfies the predicate; output is a subsequence of the input.
  - `reduce`: matches the equivalent `functools.reduce` result over the same input and accumulator.
  - `sorted`: output is a permutation of the input and is non-decreasing per the comparator; stable for equal elements.
  - `distinct`: output has no duplicate elements; output preserves the first-seen order of the input.
  - All: empty-input and single-element streams behave correctly (no exceptions, correct trivial output).
- No production code changes — this is test-only, and no spec-level behavior changes for `snakestream`'s existing capabilities.

## Capabilities

### New Capabilities
- `property-based-testing`: establishes `hypothesis`-driven property tests as a testing capability for stream operations, starting with `map`, `filter`, `reduce`, `sorted`, `distinct`.

### Modified Capabilities
(none — test-only change, no requirement changes to existing behavior)

## Impact

- `pyproject.toml`: adds `hypothesis` to `dependency-groups.dev`.
- `tests/`: new or extended test files for `map`, `filter`, `reduce`, `sorted`, `distinct`.
- CI (`.github/workflows/check.yml`): no changes needed — `uv run pytest` already picks up new test files; coverage gate is unaffected since no production code changes.
