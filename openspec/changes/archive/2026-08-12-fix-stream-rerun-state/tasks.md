## 1. Fix chain-mutation in composition

- [x] 1.1 Change `BaseStream._compose()` (`base_stream.py:43-44`) to pass a shallow copy of `self._chain` into `_sequential()` instead of the live list.
- [x] 1.2 Add a regression test asserting `len(stream._chain)` is unchanged after calling `_compose()` (directly or via a terminal op) on a `Stream` with a non-empty chain.
- [x] 1.3 Add a regression test asserting a second terminal-op call (e.g. `collect(to_list)`) on the same `Stream` instance composes against the same chain as the first call (verify via chain length or by using a chain of pure/stateless ops like `map`/`filter` against a re-iterable source such as `Stream.of([1,2,3]).map(...)`, calling `collect()` twice and asserting no `IndexError`/empty-chain artifact — see design.md's Non-Goal on source exhaustion for what "same result" means here).

## 2. Scope `distinct()`/`limit()` state to sequential composition

- [x] 2.1 In `Stream.distinct()` (`stream.py:137-149`), move `seen = set()` from the outer function body into the top of `fn`'s body, so it re-initializes on every `fn(iterable)` call.
- [x] 2.2 In `Stream.limit()` (`stream.py:163-176`), move `size = 0` from the outer function body into the top of `fn`'s body, removing the now-unnecessary `nonlocal size`.
- [x] 2.3 Add a regression test: build a `Stream` chain with `.distinct()`, compose+consume it once via `collect()`, then compose the same chain again against a fresh source (e.g. call `.distinct()` on a fresh `Stream` sharing the same underlying `fn` is not directly testable via public API — instead test via `_compose()` called twice on one `Stream` instance with a source that yields distinct-then-repeated values across two manual `_stream` reassignments, or more simply: assert two *separate* `Stream.of([...]).distinct()` instances do not share a `seen` set) — confirm second run isn't polluted by the first.
- [x] 2.4 Add the equivalent regression test for `.limit(n)` — confirm a fresh `Stream.of([...]).limit(n)` instance always allows up to `n` elements regardless of prior `Stream` instances' `limit()` usage.

## 3. Thread shared state through `ParallelStream` composition

- [x] 3.1 Design the state-holder mechanism per design.md Decision 3: a small mutable holder (e.g. a dataclass or single-item container) for `distinct()`'s `seen` set and `limit()`'s `size` counter, created per composition rather than per `.distinct()`/`.limit()` call.
- [x] 3.2 Update `distinct()`/`limit()` closures in `stream.py` to accept an optional state holder, defaulting to a fresh one when not supplied (satisfies `Stream`'s per-composition-fresh requirement from Task 2).
- [x] 3.3 Update `ParallelStream._parallel()` (`parallel_stream.py:18-43`) to create one state holder per composition and pass it to all `processes` branches' `_sequential()` calls, so all branches share the same `seen`/`size`.
- [x] 3.4 Add a regression test: `ParallelStream` chain with `.distinct()` against a source containing a duplicate element likely to be split across racing branches — assert the duplicate appears exactly once in the combined output.
- [x] 3.5 Add a regression test: `ParallelStream` chain with `.limit(n)` against a source larger than `n` — assert the combined output across all branches never exceeds `n` elements.
- [x] 3.6 Add a regression test: run the same `ParallelStream` distinct/limit chain through two separate compositions (e.g. two `.collect()` calls, or `_compose()` called twice) — assert the second composition's results aren't affected by the first composition's state.

## 4. Verification

- [x] 4.1 Run `uv run pytest` and confirm all existing and new tests pass.
- [x] 4.2 Run `uv run pytest --cov-fail-under=98` and confirm the coverage gate still passes.
- [x] 4.3 Run `uv run ruff check .` and `uv run ruff format --check .`.
- [x] 4.4 Run `uv run ty check src` and confirm no new type errors.
- [x] 4.5 Update `roadmap.md`: move both "Now" items (`_sequential()` chain destruction, per-op closure state) from **Now** to **Done**, with a summary matching the style of existing **Done** entries (per `CLAUDE.md`'s instruction to check README/roadmap parity docs).
