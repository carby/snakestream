## 1. Rename and re-shape the comparator

- [x] 1.1 Rename `_KeyComparator` to `KeyComparator` in `comparator.py` and update the import in `sort.py`; confirm `uv run ty check src` and `uv run pytest` still pass before changing anything else, so the rename is isolated from the behaviour change
- [x] 1.2 Change `KeyComparator` to hold an ordered tuple of `(key_extractor, descending)` segments instead of a single `key_extractor`, with `comparing(f)` producing one ascending segment; classify each segment's extractor independently via `is_async_callable`, per `callable-dispatch`
- [x] 1.3 Change `comparing()`'s return annotation from the `Comparator` alias to `KeyComparator`, and verify with `ty` that it is still assignable at every site accepting a `Comparator` — `sorted()`, `min()`, `max()`, `min_by()`, `max_by()`

## 2. Composition

- [x] 2.1 Add `KeyComparator.then_comparing(other)`, returning a **new** `KeyComparator`: append one ascending segment for a key extractor, or splice in every segment of another `KeyComparator` with its directions intact
- [x] 2.2 Add `KeyComparator.reversed()`, returning a **new** `KeyComparator` with every current segment's direction flipped; docstring should record why flipping each component equals negating the composite, and how that reproduces Java's before/after-chaining distinction
- [x] 2.3 Update `KeyComparator.__call__` to walk the segments, negate the sign for a descending segment, and short-circuit on the first non-zero; keep it a sync function when every segment is sync, and await only the segments classified async
- [x] 2.4 Update `comparing()`'s docstring: replace the "no `thenComparing()` here, use a tuple key" paragraph with the composition rules, and state when a tuple key is still the better answer (sync, single direction)

## 3. The sorting fast path

- [x] 3.1 Extract today's `_sort_by_key` body into `_column(extractor, arr)` returning that segment's keys, keeping the async gather and the one-time `isawaitable` trial safety net exactly as they are
- [x] 3.2 Add `_Descending` with `__slots__`, `__lt__` and `__eq__` only, with a docstring recording that tuple comparison needs no other dunder and that this is what buys per-segment direction inside a single sort
- [x] 3.3 Rewrite `_sort_by_key` to gather the k columns concurrently via `asyncio.gather(*(_column(...) ...))`, zip them into per-element tuples, and sort in three lanes: all-ascending plain, all-descending via `sort(reverse=True)`, mixed via `_Descending` on the descending columns only
- [x] 3.4 Keep the single-ascending-segment case on today's exact code path — no tuple build, no outer gather — so `add-comparator-comparing`'s measured figures still hold
- [x] 3.5 Docstring the three lanes, including why `sort(reverse=True)` is exactly comparator negation (CPython's sort is stable under `reverse=True`; it is not a post-hoc list reversal) and why the wrapper is therefore only paid for genuinely mixed directions

## 4. Tests

- [x] 4.1 Chaining: two- and three-segment chains, ties broken by the later segment, the first segment decisive when keys are distinct, and `then_comparing()` accepting another `KeyComparator` with its directions preserved
- [x] 4.2 Direction: `reversed()` on a single segment; reversal before chaining affecting only the earlier segment; reversal after chaining flipping both; double reversal restoring the original; and reversal preserving encounter order for equivalent elements (comparator negation, not output reversal)
- [x] 4.3 Immutability: composing a comparator held in a variable leaves the original ordering intact, and two compositions of one comparator are independent
- [x] 4.4 Sync/async: all-sync, all-async and mixed chains produce identical orders; an async chain works with `min()`, `max()`, `min_by()` and `max_by()`
- [x] 4.5 Extraction counts: each of k extractors invoked exactly n times by a sort, including one whose key never decides a comparison; and the direct-call path leaving the later extractor uninvoked when the first key decides
- [x] 4.6 Eagerness is observable: a later extractor that raises propagates from a sort even when all first keys are distinct
- [x] 4.7 Concurrency across segments: a chain of k `async def` extractors each awaiting an I/O-like delay completes on the order of one delay, not k sequential rounds
- [x] 4.8 The two paths agree: for every chain shape above, `min()` returns the first element of the sorted result
- [x] 4.9 Key typing: incomparable keys within one segment raise `TypeError`; segments producing unrelated key types sort fine
- [x] 4.10 Pin `sorted(comparator, reverse=True)` stacked on a `reversed()` chain, asserting the existing buffer-reversal semantics (tied elements flipped) rather than changing them

## 5. Docs and roadmap

- [x] 5.1 README `java.util.Comparator` table: move `thenComparing` and `reversed` from struck-through "decided against" to implemented rows, named `then_comparing()` and `reversed()`, noting that a chain must begin at `comparing()`
- [x] 5.2 In the same table, add `comparing(f, keyComparator)` and `thenComparing(f, keyComparator)` as struck-through deliberate skips, with the reason (Python cannot disambiguate the overload, and a comparator segment would break the every-segment-yields-a-key invariant) — so "not yet" stays distinguishable from "decided against"
- [x] 5.3 Amend the `comparing()` row's tuple-key note into the rule with its reason: tuple key for a sync single-direction ordering, chaining for async extractors or mixed directions
- [x] 5.4 Amend the `sorted()` row to distinguish `reverse=True` (buffer reversal, which flips tied elements) from `reversed()` (comparator negation, which does not)
- [x] 5.5 Add a migration-log entry: non-breaking additions plus the `_KeyComparator` -> `KeyComparator` rename of a previously-private name
- [x] 5.6 Mark roadmap open question 1 resolved and record the change in the roadmap's landed list

## 6. Validation

- [x] 6.1 `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src`
- [x] 6.2 `uv run pytest` and `uv run pytest --cov-fail-under=98`
- [x] 6.3 Measure the mixed-direction `_Descending` lane against the all-ascending lane on a representative sort and record the figure in the design or the docstring, per the project's measure-before-claiming rule
