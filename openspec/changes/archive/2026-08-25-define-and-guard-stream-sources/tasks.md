## 1. Baseline

- [x] 1.1 Confirm the two repros still fail at HEAD before changing anything: `Stream(bare_async_iter).parallel().to_array()` raises `AttributeError: ... 'aclose'`, and the same object consumed sequentially returns its elements. Repeat with an `__aiter__`-only object whose `__aiter__` returns a separate async generator.
- [x] 1.2 Confirm the current normalization baseline: `Stream.of(bytearray(b"ab")).to_array()` is `[97, 98]`, `Stream.of(memoryview(b"ab")).to_array()` is `[97, 98]`, `Stream.of(b"ab").to_array()` is `[b"ab"]`.
- [x] 1.3 Run the full suite and record the passing count, so a later "no existing test edited" claim has a baseline (`uv run pytest`).

## 2. Racing accepts every source the sequential path accepts

- [x] 2.1 In `execution.py`, widen `_maybe_aclosing()`'s parameter annotation from `AsyncGenerator` to `AsyncIterator` (importing it from `collections.abc` if not already imported). No body change — the `hasattr` check is already what makes it correct for a non-generator.
- [x] 2.2 In `race_through()`, call `aiter(source)` **once**, before the branch list comprehension, and pass the resulting iterator to every `_guarded(...)`. Do **not** put the `aiter()` call inside `_guarded()` — see design.md, "aiter() is called once in race_through()": per-branch it would give each branch an independent iterator and multiply the elements.
- [x] 2.3 Rewrite `_guarded()`'s `try/finally` to wrap its pull loop in `_maybe_aclosing()`, keeping the close under the shared lock and keeping the `StopAsyncIteration` handling and the `yield` outside the lock exactly as they are. Update its parameter annotation to match 2.1.
- [x] 2.4 Verify both repros from 1.1 now succeed under `.parallel()` and yield the same elements as a multiset as the sequential consumption.

## 3. One question per side, asked once

- [x] 3.1 In `stream.py`, collapse `_accept()` to `isinstance(source, AsyncIterable)` and drop the now-unused `AsyncGenerator` import if nothing else in the module uses it (it is also used in annotations — check before deleting).
- [x] 3.2 In `_normalize()`, replace `hasattr(source, "__iter__")` with `isinstance(source, Iterable)`, importing `Iterable` from `collections.abc`.
- [x] 3.3 Leave the `hasattr(source, "__next__")` branch as a `hasattr`, and extend its existing comment with one clause naming why: `Iterator`'s `__subclasshook__` requires both `__iter__` and `__next__`, so an object exposing only `__next__` is neither `Iterable` nor `Iterator`, and converting it would reintroduce the bug fixed at `3554cc1`.
- [x] 3.4 Run the suite: 3.1–3.3 change nothing observable, so it must pass with no test file edited.

## 4. bytearray and memoryview become scalar sources (BREAKING)

- [x] 4.1 In `_normalize()`, extend the scalar tuple to `(dict, str, bytes, bytearray, memoryview)`, keeping it as the first branch of the ladder so a `bytearray` never reaches the `Iterable` branch.
- [x] 4.2 Verify the new behaviour: `Stream.of(bytearray(b"ab")).to_array()` is `[bytearray(b"ab")]` and `Stream.of(memoryview(b"ab")).to_array()` is a single-element list holding the original `memoryview`.
- [x] 4.3 Add a README migration-log entry under `## Migration`, adjacent to the existing `str`/`bytes` entry and in the same style: what changed, that it breaks **silently**, and `Stream.of(*some_bytearray)` as the migration for callers who wanted the spread.

## 5. Tests

- [x] 5.1 In `tests/test_normalize.py` (or `tests/test_of.py`, matching where the existing `str`/`bytes` scalar cases live — check first and follow it), add cases for the `bytearray` and `memoryview` scalar scenarios from the `stream-construction` delta.
- [x] 5.2 In `tests/test_parallel.py` (or `tests/test_execution_model.py`, matching where racing-source coverage lives), add the four scenarios from the `stream-execution-model` delta: a no-`aclose()` async iterator, an `__aiter__`-returns-a-separate-iterator source, a closeable async generator still being closed under racing, and sync/scalar sources racing to the same multiset as sequential.
- [x] 5.3 Make the `__aiter__`-only test assert the **exact element multiset**, not merely the absence of `AttributeError` — that assertion is the only thing that catches the per-branch-`aiter()` mistake in 2.2, which passes an error-free test while yielding `workers ×` the elements.
- [x] 5.4 Confirm no existing test file was edited. New files and new cases appended to the two files named in 5.1/5.2 are expected; an edit to an existing assertion anywhere is a signal the change went wider than this story.

## 6. Validation

- [x] 6.1 `uv run pytest` — all green, count is the 1.3 baseline plus the new cases.
- [x] 6.2 `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src`.
- [x] 6.3 `uv run pytest --cov-fail-under=98`.
- [x] 6.4 `openspec validate define-and-guard-stream-sources --strict`.
- [x] 6.5 No benchmark run: every site here executes once per stream construction or once per racing branch, never per element (proposal.md — Impact).
- [x] 6.6 Move the story out of roadmap.md's **Now** table into **Done**, with what was decided (`bytearray`/`memoryview` scalar), what was deliberately not done (the `__next__` branch), and the archive path.
