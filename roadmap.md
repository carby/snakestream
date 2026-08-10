# Roadmap

Now/Next/Later view of open code-quality and test-rigor items, generated from
the review-pass notes below. Completed items from that review remain in
**Done** for history.

## Now

Small, low-risk, high-confidence — no public API impact.

| Item | Why now |
|---|---|
| **Add `mypy` (or `pyright`) to CI** | Codebase is fully type-hinted already; nothing currently checks that the hints stay true. Cheap to add, catches drift immediately. |
| **Add an install/import smoke test across the Python matrix** — `pip install .` + bare `import snakestream` on each of 3.10–3.14, not just running pytest against checked-out source. | A packaging mistake could pass CI today while breaking real installs. Low effort, closes a real gap. |

## Next

Real design/implementation work, but contained — mostly additive or scoped to
one area.

| Item | Why next |
|---|---|
| **Add property-based tests with `hypothesis`** for `map`, `filter`, `reduce`, `sorted`, `distinct` | Cheaply catches edge cases hand-written tests miss (empty inputs, duplicate keys, non-comparable types, single-element streams). Needs some setup but no API changes. |
| **Simplify `Stream.of()`** — currently branches on dict vs. list vs. multiple positional args vs. kwargs into one `source` list (`stream.py:36-59`); unclear what `Stream.of(1, [2, 3])` or `Stream.of(a=1, b=2)` produce without tracing the logic. | Worth splitting into narrower, clearer construction paths. Touches public API — needs a design decision on the replacement shape before implementation. |
| **Rename or re-scope `.parallel()` / `PROCESSES`** — currently just `asyncio` tasks racing over a shared generator (I/O-bound only, GIL-bound, no multiprocessing), but the naming implies real OS-thread parallelism like Java's `parallelStream()`. | Misleading naming is a correctness-of-understanding risk for callers. Decide: rename/docstring to set correct expectations, or build an actual multiprocessing-backed implementation. Either path is a breaking-rename candidate — track in README's pre-1.0 migration log per `CLAUDE.md`. |

## Later

Bigger, structural — needs explicit buy-in before starting since it changes a
core semantic.

| Item | Why later |
|---|---|
| **Decide mutable-builder vs. immutable-pipeline semantics** — every intermediate op (`filter`, `map`, `distinct`, etc.) does `self._chain.append(fn); return self`, mutating the instance rather than returning a new one. Diverges from Java's immutable stream semantics; a `Stream` reference can't be safely reused or forked once chaining starts. | Highest blast radius of any item here — affects every consumer of the chain-of-closures model described in `CLAUDE.md`. Needs an explicit decision (keep and document current behavior vs. change to return-new-instance-per-op) before any code moves, since it's a breaking change either way. |

## Done

- Verified `--cov-fail-under=98` already enforces combined line+branch
  coverage, not line coverage alone: `[tool.coverage.run] branch = true`
  folds branch-arc misses into the same "percent covered" figure the gate
  reads, confirmed by observing a deliberately partial branch drop the
  reported percentage. No code change needed; added a comment in
  `pyproject.toml` recording the finding so it doesn't need re-deriving.
- `min()`/`max()` used to silently skip falsy candidate values (`0`, `""`,
  `False`) because of a truthiness check in `Stream._min_max`. Fixed by
  replacing the `None`-as-sentinel logic with a proper `_UNSET` sentinel.
- `parallel()` pipelines left orphaned `asyncio` tasks (and "Task exception
  was never retrieved" warnings) when one branch raised mid-stream. Fixed in
  `ParallelStream._parallel` by cancelling and draining remaining tasks in a
  `finally` block.
- Test infra was silently dropping tests on a clean install: `pytest-mock`
  was missing from `setup.cfg`'s `testing` extra, and the `async_int_to_letter`
  fixture in `conftest.py` wasn't decorated for strict-mode `pytest-asyncio`.
  Both fixed; added regression tests for the two bugs above
  (`test_min.py`, `test_max.py`, `test_exception.py`).
- `Stream.of()` had a dead branch, `if args and len(args) == 0: pass`
  (`stream.py:40-41`), which could never be true and just duplicated the
  no-op fallthrough of the `else` branch. Removed.
- The `TYPE_CHECKING`-only import in `stream.py:17` used an unqualified
  `from stream_builder import StreamBuilder`, which would fail if ever
  actually evaluated. Fixed to `from snakestream.stream_builder import
  StreamBuilder`.
- Added tests covering the async-predicate short-circuit branches of
  `all_match`, `none_match`, and `any_match` (`stream.py:255,267,283`) that
  were previously only exercised by synchronous predicates.
- Added a `--cov-fail-under=98` gate so a coverage regression now fails CI
  instead of silently passing. Enforced only on the newest Python version
  in `check.yml`'s matrix (not via `setup.cfg`'s `addopts`), since
  `coverage.py`'s branch-arc measurement for `async for` loops differs
  across CPython versions and produced spurious failures on 3.8/3.9.
- Fixed `deliver.yml` to target `master` instead of `main`, since the repo's
  default branch is `master` and the workflow was never triggering.
- Pinned GitHub Actions to commit SHAs and added concurrency guards to CI
  workflows.
- Added `pip-audit` dependency-vulnerability scanning and `ruff format`
  enforcement to CI.
