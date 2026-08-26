## 1. Rename in source

- [x] 1.1 Rename `Stream.is_ordered()` to `Stream._is_ordered()` in
  `src/snakestream/stream.py`, body and docstring reasoning unchanged
- [x] 1.2 Update the single internal call site, `for_each_ordered()` in
  `stream.py`, to the private name
- [x] 1.3 Confirm no other module references it (`grep -rn is_ordered src/`
  should return only `stream.py`), and that nothing exports it from
  `__init__.py`
- [x] 1.4 `uv run ruff check . && uv run ruff format --check . && uv run ty check src`

## 2. Rework the ordering tests

All twenty references live in `tests/test_unordered.py`; no other test file
names the accessor.

- [x] 2.1 Rewrite the `sorted()`/`unordered()` restoration tests
  (`test_sorted_after_unordered_is_ordered_again`,
  `test_unordered_after_sorted_is_unordered`,
  `test_unordered_between_two_sorts_is_ordered`,
  `test_ops_after_a_sort_preserve_the_restored_ordering`) to assert the
  behavioural observable — `find_first()` on a racing sorted pipeline, per the
  spec's rewritten scenarios — rather than the accessor's return value
- [x] 2.2 Rewrite `test_is_ordered_default_sequential`,
  `test_is_ordered_default_parallel`,
  `test_is_ordered_true_for_a_chain_of_order_preserving_ops` and
  `test_unordered_sets_is_ordered_false` behaviourally, naming them for the
  behaviour they now assert
- [x] 2.3 Keep the four mode-switch tests
  (`test_unordered_survives_parallel_switch`,
  `test_unordered_survives_sequential_switch`,
  `test_ordered_stays_true_across_parallel_switch`,
  `test_ordered_stays_true_across_sequential_switch`) asserting on
  `_is_ordered()`, with a comment naming the design decision that no behavioural
  observable exists for mode-switch survival
- [x] 2.4 **Verify each rewritten test actually pins the rule**: temporarily
  invert the fold in `stream.py` (start from unordered, or make `_SortedOp`
  preserve rather than set) and confirm every rewritten test fails; revert. A
  behavioural test that still passes under an inverted fold is not testing
  ordering — replace it or fall back to a `_is_ordered()` assertion per the
  design's stated exception
- [x] 2.5 Add a test asserting the public accessor is gone —
  `hasattr(stream, "is_ordered")` is `False` — per the new spec requirement
- [x] 2.6 `uv run pytest` clean, and `uv run pytest --cov-fail-under=98` still
  passes

## 3. Documentation

- [x] 3.1 README: change the `is_ordered()` parity row to a struck-through
  not-in-Java row alongside the existing `ordered()` row, explaining that Java
  exposes only `isParallel()` and keeps `ORDERED` in the package-private
  `StreamOpFlag`
- [x] 3.2 README: add a `0.3.5 -> next` migration-log entry for the removal,
  next to the two existing ordering entries — state that the break is loud
  (`AttributeError`), that there is no alias, and that a caller who needs the
  distinction should express it through `unordered()`/`sorted()` and the
  order-sensitive terminals
- [x] 3.3 `CLAUDE.md`: fix the executor section, which is already stale — it
  says `find_first()` consults the accessor when it has named `SEQUENTIAL`
  unconditionally since `make-ordering-a-chain-characteristic`. State the one
  remaining caller, `for_each_ordered()`, under the private name
- [x] 3.4 Check the README `unordered()`, `sorted()`, `for_each_ordered()` and
  `find_first()` rows for stray `is_ordered()` mentions

## 4. Close out

- [x] 4.1 `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run ty check src` all clean
- [x] 4.2 `openspec validate make-is-ordered-internal`
- [x] 4.3 Archive the change, then sweep the main spec by hand: rewrite
  `openspec/specs/stream-ordering/spec.md`'s `## Purpose` (it names
  `is_ordered()` twice) and rename the three scenarios carried through the delta
  under their old accessor-spelling names, dropping their "retained for
  continuity" notes
- [x] 4.4 Move the roadmap's **Now** entry to **Done**, recording what the rework
  of the spec scenarios found — in particular whether any behavioural rewrite
  failed the task 2.4 inversion check and had to keep an accessor assertion
