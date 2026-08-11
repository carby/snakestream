## Context

Snakestream's intermediate ops (`map`, `filter`, `sorted`, `distinct`) queue closures onto `self._chain` (`stream.py`) and only execute when a terminal op like `collect()` drives `self._compose()`; `reduce` is itself a terminal op. All accept sync or async user-supplied callables. Existing tests in `tests/` are example-based (fixed lists, fixed predicates/mappers). This change adds `hypothesis`-driven tests asserting the general invariants each operation must hold, independent of the specific example chosen.

## Goals / Non-Goals

**Goals:**
- Add `hypothesis` as a dev dependency.
- Add property tests for `map`, `filter`, `reduce`, `sorted`, `distinct` that generate varied inputs (including empty and single-element streams) and assert invariants against a plain-Python reference (e.g. `list`/`sorted`/`functools.reduce`), not against snakestream's own internals.
- Keep tests async (`pytest-asyncio`, matching existing test style) and run them through `Stream.of(...).collect(to_list)` like the existing example tests do.
- Cover both sync and async user-supplied callables for at least one property per operation, since `stream.py` branches on `iscoroutinefunction(...)`.

**Non-Goals:**
- No production code changes; this is test-only.
- No property tests for other operations (`flat_map`, `peek`, `limit`, etc.) — out of scope, could be a future roadmap item.
- No fuzzing of `ParallelStream` — parallel mode doesn't preserve ordering, which complicates permutation/equality assertions; sticking to `Stream` (sequential) keeps invariants straightforward.
- Not chasing 100% exhaustive `hypothesis` strategies (e.g. arbitrary user classes) — use simple, well-supported strategies (ints, text, small lists) sufficient to catch the edge cases roadmap.md calls out.

## Decisions

- **Reference-oracle style**: each property test compares snakestream's output to the equivalent plain-Python computation (`map`→`list(map(...))`, `filter`→`list(filter(...))`, `reduce`→`functools.reduce`, `sorted`→`sorted(...)`, `distinct`→dict-based dedup preserving order) rather than re-deriving invariants by hand. This is simpler to get right and matches what these operations are supposed to do.
  - Alternative considered: pure invariant-checking (e.g. "output length == input length" for `map`) without an oracle. Rejected as the sole approach because it's weaker — oracle comparison also catches ordering/value bugs, and Python's stdlib equivalents are trivial to write correctly.
- **File layout**: extend the existing `test_map.py`, `test_filter.py`, `test_reduce.py`, `test_sorted.py`, `test_distinct.py` with `@given`-decorated test functions rather than creating parallel `test_*_hypothesis.py` files.
  - Alternative considered: separate files per the proposal's mention. Rejected in favor of colocating with existing example tests for the same operation — easier to see all coverage for one op in one place, consistent with this repo's one-file-per-operation convention.
- **Strategies**: use `st.lists(st.integers())`, `st.lists(st.text())`, and similar built-in composable strategies; for `sorted`, generate lists of tuples or use a comparator over ints to test non-comparable-type resilience only where `stream.py`'s `sorted` explicitly supports a custom `Comparator` (it does — `comparator: Comparator | None = None`).
- **Async coverage**: for each operation, parametrize or duplicate one property test to pass an `async def` predicate/mapper/accumulator/comparator, exercising the `iscoroutinefunction()` branch already covered structurally by existing example tests (e.g. `test_all_match.py`'s async-predicate tests) — same pattern, applied to the five ops in scope.

## Risks / Trade-offs

- [Flaky/slow CI from large generated inputs] → Use `hypothesis`'s default settings (bounded example count) and small strategies (`st.integers()`, short lists); no need to override `max_examples` unless CI timing shows a problem.
- [`distinct`'s dedup semantics on non-hashable elements] → Existing `distinct()` implementation's exact dedup mechanism should be checked before writing the oracle; if it relies on hashing, restrict generated elements to hashable types (ints, strings, tuples).
- [`sorted`'s comparator-sign contract] → `CLAUDE.md`/roadmap history shows this was a recent bugfix (comparator sign interpretation, tie-break behavior); the property test must assert the *current, fixed* contract (3-way int comparator, first-of-equal-elements order preserved) to avoid re-introducing confusion, not the old buggy one.

## Open Questions

None — scope is self-contained per roadmap.md, and no API changes are needed.
