## 1. Segment representation

- [x] 1.1 Widen the `Segment` alias into a tagged union carrying either a key extractor or a raw supplied comparator alongside `descending`, and add the extractor-plus-comparator alias to `type.py` rather than inline (design Decision 1, 6); verify `uv run ty check src` passes and every existing test in `tests/test_comparing.py` and `tests/test_sorted.py` still passes unchanged
- [x] 1.2 Teach `KeyComparator.__init__` to classify a comparator segment without treating it as an extractor, so `_is_async`/`_any_async` stay correct for a chain mixing both kinds; verify an existing all-extractor chain's async classification is byte-identical to today's

## 2. Construction surface

- [x] 2.1 Add arity-based classification of a bare callable in `then_comparing()` — one positional parameter means key extractor, two means comparator, indeterminate (`*args`) means key extractor, `isinstance(KeyComparator)` taking precedence (design Decision 4); verify with tests covering every row of that decision's table
- [x] 2.2 Widen `then_comparing()` to accept a bare `Comparator` and produce a comparator segment; verify the tie-break scenarios in `comparator-key-comparator`'s first requirement
- [x] 2.3 Add the optional second positional `key_comparator` parameter to `comparing()` and `then_comparing()`, lowering both onto a comparator segment over the extracted key (design Decision 6); verify the two-argument scenarios in `comparator-key-comparator`'s second requirement, including keys with no natural ordering
- [x] 2.4 Reject an async callable in either comparator position at construction with a `StreamBuildException` naming both supported alternatives (design Decision 2); verify the three rejection scenarios, and that `comparing(async_extractor, sync_comparator)` is accepted

## 3. Sorting path

- [x] 3.1 Build `cmp_to_key(_checked(c))` for a comparator segment where that segment's column is built in `sort.py`, leaving `_checked()` and the `comparator.py` -> `sort.py` import direction untouched (design Decision 1); verify a single comparator segment sorts correctly and that `split-sort-into-comparator-and-sort`'s import edge is unchanged
- [x] 3.2 Verify a comparator segment rides all three direction lanes and the tolerant column unchanged — plain ascending, `reverse=True`, `_Descending` in a mixed chain, and as the second component of a `(present, key)` tuple — with a test per lane
- [x] 3.3 Extend the raising path of the comparator-segment wrapper to name the async rejection when it sees a coroutine, catching a callable that `is_async_callable` cannot (design Decision 3); verify a plain `def __call__` returning a coroutine raises with the async-rejection message rather than "comparator must return an int"

## 4. Direct-comparison path

- [x] 4.1 Teach `_compare_sync` and `_compare_async` to invoke a comparator segment directly rather than through a key, checking its sign once (design Decision 1); verify `min()`, `max()`, `min_by()` and `max_by()` return the first and last elements of the order `sorted()` produces for the same chain
- [x] 4.2 Verify the bool contract holds on both paths for a supplied comparator and for a supplied key comparator — `TypeError` from `sorted()` and from a direct invocation

## 5. Composition

- [x] 5.1 Verify reversal composes: `reversed()` after a comparator segment negates it along with every other component, and `reversed()` before chaining flips only the earlier ordering (design Decision 5)
- [x] 5.2 Verify null tolerance composes: a `None` element in a null-tolerant chain containing a comparator segment is placed at the declared end and the supplied comparator is never invoked with it (design Decision 5)
- [x] 5.3 Verify `nulls_first(cmp)`/`nulls_last(cmp)` passed to `then_comparing()` is recognised as a comparator and orders elements rather than raising `TypeError` on argument count
- [x] 5.4 Verify stability: elements a chain containing a comparator segment treats as equivalent come out in encounter order, sequentially and under `parallel()`
- [x] 5.5 Verify the fast path and `__call__` agree for every shape — bare comparator segment, two-argument form, reversed before and after chaining, mixed directions, null-tolerant, and on ties — the drift risk named in design's Risks

## 6. Documentation and gates

- [x] 6.1 Update README's `java.util.Comparator` table: move `then_comparing(comparator)` from not-yet-implemented and `comparing(f, keyComparator)`/`thenComparing(f, keyComparator)` from struck-through to implemented, and restate the signatures on the existing `comparing`/`then_comparing` rows; verify no Migration entry is added, since nothing breaks
- [x] 6.2 Run the full gate as CI does — `uv run pytest`, `uv run pytest --cov-fail-under=98`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src` — and verify all pass
