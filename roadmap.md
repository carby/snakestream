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
