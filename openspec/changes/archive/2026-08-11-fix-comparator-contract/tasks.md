## 1. Type alias

- [x] 1.1 Change `Comparator` in `src/snakestream/type.py` from `Callable[[T, T], bool | Awaitable[bool]]` to `Callable[[T, T], int | Awaitable[int]]`.

## 2. min()/max() logic

- [x] 2.1 Rewrite `Stream.max()` in `src/snakestream/stream.py` to update `found` when `comparator(n, found) > 0` (sync and async branches), removing the bool-truthy check.
- [x] 2.2 Rewrite `Stream.min()` to update `found` when `comparator(n, found) < 0` directly, removing the `negative_comparator` wrapper closures.
- [x] 2.3 Update `_min_max()`'s signature/usage as needed to support the direct sign-check callers from 2.1/2.2.
- [x] 2.4 Remove the now-stale `# ty can't narrow...` comment in `sorted()` if it no longer applies once the alias is `int`-typed; re-run `uv run ty check src` to confirm no new narrowing issues.

## 3. Tests

- [x] 3.1 Add/update tests for `max()` with a 3-way comparator asserting correct selection (e.g. `Stream.of([3,1,2]).max(lambda a,b: a-b) == 3`).
- [x] 3.2 Add/update tests for `min()` with a 3-way comparator asserting correct selection (e.g. `Stream.of([3,1,2]).min(lambda a,b: a-b) == 1`).
- [x] 3.3 Add tests asserting `min()` and `max()` both keep the first of tied elements.
- [x] 3.4 Add async-comparator variants of the above for `min()`/`max()`/`sorted()` if not already covered.

## 4. Docs

- [x] 4.1 Update README.md's parity table / type references for the corrected `Comparator` contract.
- [x] 4.2 Add an entry to README's pre-1.0 migration log documenting the `min()`/`max()` breaking behavior change (bool comparator callers must switch to 3-way).
- [x] 4.3 Update `roadmap.md` to mark the comparator finding resolved (remove or move out of Now).

## 5. Verification

- [x] 5.1 Run `uv run pytest` and confirm the full suite passes.
- [x] 5.2 Run `uv run ruff check .` and `uv run ruff format --check .`.
- [x] 5.3 Run `uv run ty check src`.
- [x] 5.4 Run `uv run pytest --cov-fail-under=98`.
