## 1. Types and the factory

- [x] 1.1 Add a `KeyExtractor` alias to `type.py` — `Callable[[T], Any | Awaitable[Any]]`, following the existing sync-or-async convention of `Mapper` and friends, with a comment noting it returns an ordering *key*, not a comparison sign
- [x] 1.2 Add the object `comparing()` returns to `comparator.py`: exposes the extractor as an attribute for `sort()` to unwrap, and implements `__call__(a, b) -> int` with the ordinary two-extractions-and-compare semantics
- [x] 1.3 Add the `comparing(key_extractor)` factory to `comparator.py` with a docstring covering: why it returns an object rather than a closure (a closure would cost `2n log n` awaits — see design.md), and the tuple-key workaround for multi-key ordering since `thenComparing()` is out of scope
- [x] 1.4 Confirm `comparator.py` gained no import from `sort.py` — the one-way edge (sorting calls semantics, never the reverse) must hold

## 2. The sort fast path

- [x] 2.1 Add the key fast path to `sort()` in `sort.py`, ahead of the existing `is_async_callable` dispatch: unwrap the extractor, extract keys, decorate–sort–undecorate
- [x] 2.2 Sort on the key alone (an explicit key selector over the paired list), never on the `(key, element)` tuple — Timsort's stability then gives encounter order for free, and elements that don't support `<` still sort
- [x] 2.3 Classify the extractor's awaitability once per call via `is_async_callable`, with the standard one-time `isawaitable` safety net; do **not** add a trial-comparison probe — key extraction runs inside an `async` loop where an `await` is always available
- [x] 2.4 Verify no `check_comparator_result_type` / `_checked` call reaches the key path, and that an incomparable-key `TypeError` propagates from `list.sort` unwrapped
- [x] 2.5 Confirm `merge_sort`, `_merge`, `_checked` and the trial probe are untouched, and that a non-`comparing()` comparator still takes exactly the path it does today

## 3. Tests

- [x] 3.1 `sorted()` with a sync and an async `comparing()` extractor produces the expected order (spec: builds a Comparator from a key extractor; extractor may be sync or async)
- [x] 3.2 `min()`, `max()`, `min_by()` and `max_by()` all accept a `comparing()` comparator, sync and async extractor (spec: accepted anywhere a Comparator is)
- [x] 3.3 The returned object called directly with two elements returns a correctly-signed `int` (spec: callable as an ordinary Comparator)
- [x] 3.4 **Drift test:** for the same `comparing()` comparator, the sorted order matches the order produced by sorting through its `__call__` path — asserted on ties and on `bool`/`None`/mixed-key inputs (design.md's first risk)
- [x] 3.5 Extractor invocation count is exactly n for a stream of n elements (spec: applied once per element) — the guarantee the capability exists for, so this test is not optional
- [x] 3.6 Stability: equal keys retain encounter order (spec scenario `[("a",1),("b",1),("c",0)]` → `[("c",0),("a",1),("b",1)]`)
- [x] 3.7 Incomparable keys raise `TypeError`; a `bool`-valued key sorts `False` before `True` without error (spec: keys must be mutually comparable)
- [x] 3.8 Elements that do not themselves support `<` sort correctly when their keys do — pins task 2.2's key-selector choice
- [x] 3.9 `sorted(comparing(...), reverse=True)` — pin the existing reverse-the-buffer semantics (equal-key runs reverse too), matching what comparators do today
- [x] 3.10 A `comparing()` comparator works under `.parallel()` as it does sequentially, and downstream of `unordered()` where `sorted()` restores ordering
- [x] 3.11 Empty stream and single-element stream through the key path

## 4. Docs and gates

- [x] 4.1 Add a `java.util.Comparator` parity table to README.md's API section — a third table alongside `Stream` and `Collectors`, recording `comparing()` as implemented
- [x] 4.2 In that table, record `thenComparing`, `reversed`, `naturalOrder` and `reverseOrder` as deliberately skipped with their reasons, in the struck-through style the `Stream` table uses — so "not yet" is distinguishable from "decided against"
- [x] 4.3 Settle design.md's open question on sequential vs. `asyncio.gather` extraction with a benchmark; record the figures and the decision in design.md
- [x] 4.4 Run the full gate: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`, `uv run ty check src`, `uv run pytest --cov-fail-under=98`
- [x] 4.5 Update roadmap.md — note that `comparing()` landing is the precondition for reassessing the async comparator and `merge_sort` (proposal.md's out-of-scope items)
