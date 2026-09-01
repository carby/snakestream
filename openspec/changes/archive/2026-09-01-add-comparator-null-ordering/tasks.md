## 1. Null placement on the comparator

- [x] 1.1 Add a null-placement enum to `comparator.py` (absent / first / last) beside `Segment`, per design Decision 6; verify `uv run ty check src` passes with it unused
- [x] 1.2 Give `KeyComparator` a null-placement field defaulting to absent, so every existing `comparing(f)` call constructs exactly what it constructs today; verify the full `uv run pytest` suite passes unchanged before any behaviour is added
- [x] 1.3 Carry the field through `then_comparing()` onto the returned comparator, and docstring the deliberate divergence from Java recorded in design Decision 1 (Java's `nullsFirst(c).thenComparing(b)` calls `b` on the nulls and throws); verify with a test that a tie-break appended to a tolerant chain is itself tolerant
- [x] 1.4 Leave `reversed()` flipping segment directions only — no null-specific rule — and docstring why that already moves the nulls (design Decision 3); verify with a test that reversing a nulls-first ordering places nulls last

## 2. The factories

- [x] 2.1 Add `nulls_first(comparator=None)` and `nulls_last(comparator=None)` to `comparator.py`, dispatching on the argument per design Decision 4: a `KeyComparator` gets the field set, any other `Comparator` gets a plain wrapping comparator, nothing gets a `KeyComparator` over a constant key; verify each of the three arms with a test
- [x] 2.2 Classify a wrapped plain comparator sync/async once at construction via `is_async_callable` per `callable-dispatch`, producing an async wrapper for an async comparator; verify with a test that an async wrapped comparator sorts and that its result type is still checked against `comparator-contract`
- [x] 2.3 Add `@overload` signatures so `ty` sees `KeyComparator` in and `KeyComparator` out, `Comparator` in and `Comparator` out; verify `uv run ty check src` and add a case to `tests/typing/`
- [x] 2.4 Docstring both factories against `Comparator.nullsFirst`/`nullsLast`, stating that they also tolerate a null *key*, which Java reaches only through the declined `comparing(f, keyComparator)` overload

## 3. The sorting fast path

- [x] 3.1 Change `_column()` to yield `None` for a `None` element rather than invoking the extractor on it, keeping the async gather and the one-time `isawaitable` trial intact; verify with a test that the extractor is never called with `None`
- [x] 3.2 Build a tolerant column as `(present, key)` with the constants chosen by placement, testing presence with `is None` and never truthiness; verify with a test that `0`, `False` and `""` keys sort as keys and not as nulls
- [x] 3.3 Route a tolerant `KeyComparator` through the existing three direction lanes unchanged — no fourth lane — and confirm `_Descending` handles a tuple key; verify with tests covering all-ascending, all-descending and mixed chains that tolerate nulls
- [x] 3.4 Keep an intolerant comparator on today's exact code path, single-ascending-segment lane included, so `add-comparator-comparing`'s figures still hold; verify by running the existing `test_comparing.py` and `test_sorted.py` unchanged
- [x] 3.5 Measure the tolerant single-segment lane against the plain-key lane (design's Open Question) and record the figure in `_sort_by_key`'s docstring alongside the existing lane measurements

## 4. The `__call__` path

- [x] 4.1 Apply the same null rules in `KeyComparator.__call__` — null element and null key at the placed end, two nulls equal, fall through to the next segment — keeping it a sync function when every segment is sync; verify with a test that `min()` over a stream containing `None` returns `None` under `nulls_first` and the smallest value under `nulls_last`
- [x] 4.2 Verify the fast path and `__call__` agree, per the spec's last requirement: a property-based test over the matrix of first/last x reversed/not x chained/not x null-element/null-key, asserting the pairwise signs are consistent with the sorted order and that ties keep encounter order

## 5. Terminals and collectors

- [x] 5.1 Verify a nulls-tolerant comparator is accepted unchanged by `min()`, `max()`, `min_by()` and `max_by()` with no signature change, including the first-of-tied rule `is_new_extremum` implements; add tests for each
- [x] 5.2 Verify a nulls-tolerant `sorted()` behaves identically under `.parallel()`, sorting the whole stream rather than each branch's subset, matching the existing parallel `sorted()` tests

## 6. Documentation

- [x] 6.1 Replace README's `nulls_first(comparator) / nulls_last(comparator)` row with an implemented row covering both the null-element and null-key cases, the composition rules, and the `reversed()` interaction; verify the row's shape matches the rest of the `Comparator` table
- [x] 6.2 Add a README Migration-log entry recorded as **not breaking**, per project rule, in the same commit as the change
- [x] 6.3 Retire roadmap gap 5 from **Now** -> **Queued changes** with a note on what shipped and what it decided, matching how gaps 2 and 3 were retired on 2026-09-01
- [x] 6.4 Update `CLAUDE.md`'s Collectors/Comparator architecture notes only if the null-placement field changes what the module summary claims; skip if it does not

## 7. Gates

- [x] 7.1 Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src` and `uv run pytest --cov-fail-under=98`, matching what CI runs on the 3.14 leg
- [x] 7.2 Run `openspec validate add-comparator-null-ordering --strict` and confirm every spec scenario has a test that exercises it
