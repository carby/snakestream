# Roadmap

Notes from a review pass on test coverage and general code clarity. Items are
grouped by status.

## Done

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
- Added `--cov-fail-under=98` to `setup.cfg`'s `addopts` so a coverage
  regression now fails CI instead of silently passing.
- Fixed `deliver.yml` to target `master` instead of `main`, since the repo's
  default branch is `master` and the workflow was never triggering.

## To revisit

- **`Stream.of()` is overloaded and hard to reason about.** It branches on
  dict vs. list vs. multiple positional args vs. kwargs, all folded into one
  `source` list with special-casing (`stream.py:36-59`). Not obvious what
  `Stream.of(1, [2, 3])` or `Stream.of(a=1, b=2)` produce without tracing the
  logic by hand. Also has a dead branch (`args and len(args) == 0` can never
  be true). Worth splitting into clearer, narrower construction paths.

- **"Parallel" is misleading naming.** `.parallel()` and the `PROCESSES`
  constant suggest real CPU parallelism (as in Java's `parallelStream()`,
  which uses multiple OS threads), but this is just `asyncio` tasks racing
  over a shared generator — useful for I/O-bound coroutines, but it won't
  speed up CPU-bound work at all (GIL-bound), and there's no multiprocessing
  anywhere in the codebase. Needs either a rename/docstring to set correct
  expectations, or an actual multiprocessing-backed implementation.

- **Streams are mutable builders, not immutable pipelines.** Every
  intermediate op (`filter`, `map`, `distinct`, etc.) does
  `self._chain.append(fn); return self` — mutating the same instance rather
  than returning a new one. This diverges from Java's immutable stream
  semantics and means a `Stream` reference can't be safely reused or forked
  once chaining has started. Worth deciding explicitly whether this is
  intended behavior (and documenting it) or worth changing to return new
  instances per intermediate op.

## Testing & verification

Coverage is already strong (123 tests, 99.58% line/branch), so these are
about closing the remaining gaps and hardening the process, not building
from scratch.

- **No static type checking in CI.** The codebase is fully type-hinted
  (`type.py`, generics in `Stream`/`ParallelStream`) but nothing runs
  `mypy`/`pyright`, so annotations can drift from reality unnoticed. Worth
  adding a `mypy` step to `check.yml`.

- **No property-based testing.** For a streams library (`map`, `filter`,
  `reduce`, `sort`, `distinct`), `hypothesis` would cheaply catch edge cases
  hand-written tests tend to miss — empty inputs, duplicate keys,
  non-comparable types, single-element streams.

- **No install/import smoke test across the Python matrix.** `check.yml`
  runs `pytest` against the checked-out source on Python 3.8–3.12, but
  never does a `pip install .` + bare `import snakestream` on each version.
  A packaging mistake (e.g. a missing entry in `packages.find`, a
  Python-version-conditional import) could pass CI while breaking for
  actual installs.

- **Line coverage is gated, branch coverage isn't (once `--cov-fail-under`
  is added).** `.coveragerc` sets `branch = True`, so branch coverage is
  already measured, but a single `--cov-fail-under` threshold on total
  coverage can mask a drop in branch coverage specifically (e.g. an
  untested `if`/`else` side) as long as line coverage stays high. Worth
  confirming the fail-under threshold is read against combined
  line+branch, or gating branch coverage explicitly.
