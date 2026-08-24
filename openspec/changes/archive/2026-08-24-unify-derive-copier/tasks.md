## 1. Merge the copiers

- [x] 1.1 Replace `_derive(self, chain)` and `_derive_executor(self, executor)` in `stream.py` with a single `_derive(self, chain: list[Op], executor: Executor) -> Stream[Any]`, preserving the check-before-copy / consume-after-copy ordering.
- [x] 1.2 Update the eight intermediate ops (`filter`, `map`, `flat_map`, `sorted`, `distinct`, `peek`, `limit`, `skip`) to call `self._derive(self._chain + [op], self._executor)`.
- [x] 1.3 Update `parallel()` to call `self._derive(self._chain, RACING)` and `sequential()` to call `self._derive(self._chain, SEQUENTIAL)`.
- [x] 1.4 Move `_derive_executor()`'s "must not compose, must not assign onto self" docstring content onto `parallel()` and `sequential()`.
- [x] 1.5 Remove the now-unused `_derive_executor()` method.

## 2. Verify

- [x] 2.1 Run `uv run pytest` and confirm the full suite passes with no test file edited (`git diff --stat tests/` empty).
- [x] 2.2 Run `uv run ruff check .` and `uv run ruff format --check .`.
- [x] 2.3 Run `uv run ty check src`.
- [x] 2.4 Grep for `_derive_executor` across `src/` and `openspec/specs/` to confirm no stale reference remains.

## 3. Close out

- [x] 3.1 Update `roadmap.md`: move this item from **Now** to **Done**, following the existing entry format (what landed, why, verification notes).
- [x] 3.2 Run `openspec validate --strict` for this change.
