# Roadmap

Now/Next/Later view of open code-quality and test-rigor items, generated from
the review-pass notes below. Completed items from that review remain in
**Done** for history.

## Now

Actively being picked up. Mostly low-risk and self-contained, but may
include a public-API item once there's a specific, near-term plan to do
the design work.

| Item | Why now |
|---|---|
| **Simplify `Stream.of()`** — currently branches on dict vs. list vs. multiple positional args vs. kwargs into one `source` list (`stream.py:36-59`); unclear what `Stream.of(1, [2, 3])` or `Stream.of(a=1, b=2)` produce without tracing the logic. Decide the `str`/`bytes` case as part of the same redesign: `_normalize` (`base_stream.py:15`) treats any `__iter__` as a sequence, so `Stream.of("abc")` yields `['a', 'b', 'c']` and `Stream.of(b"ab")` yields `[97, 98]` rather than one scalar element. | Worth splitting into narrower, clearer construction paths. Touches public API — needs a design decision on the replacement shape before implementation; track any resulting rename in README's pre-1.0 migration log per `CLAUDE.md`. |
| **Stop `_sequential()` from destroying `self._chain`** — `base_stream.py:38,40` calls `pop(0)` on the caller's live list, so `_compose()` empties the chain and a second terminal op on the same stream yields nothing (`collect -> [2,4,6]`, then `collect -> []`). `ParallelStream._parallel` already passes a copy (`intermediaries[:]`, `parallel_stream.py:21`), so the same `_compose()` contract behaves differently per subclass. | One-line fix (`intermediaries[:]`, or replace the recursion with an iterative loop and also drop the O(len(chain)) stack frames). Adjacent to the mutable-builder item in **Later** but independent of it: that one is about intermediate ops doing `return self`, this is unintended mutation inside compose, and it can be fixed without pre-deciding the larger semantic question. **Does not on its own make a second terminal op work** — the build-time-closure-state item below blocks that too, and both must land together to actually fix re-collection. |
| **Move per-op closure state inside the closure** — `distinct()` creates `seen = set()` and `limit()` creates `size = 0` *outside* the `async def fn` they append to `_chain` (`stream.py:155-194`), so the state belongs to the chain entry rather than to a run of the pipeline. Applying the same closure to two fresh sources gives `[1,2,3,4,5]` then `[]` for `distinct`, and `[1,2]` then `[]` for `limit`. | Hidden blocker for the chain-mutation item above: applying the `intermediaries[:]` fix alone still leaves a second `collect()` returning `[]`, just for this reason instead. Fix is to initialize the state inside `fn`, but it interacts with `ParallelStream`, where all branches currently share one closure object — a shared `seen`/`size` is what makes parallel `distinct`/`limit` behave sanely today, and per-branch copies change those semantics. Decide together with the item above. |
| **Replace `iscoroutinefunction()` dispatch with a `_maybe_await` helper** — the `if iscoroutinefunction(x): await x(...) else: x(...)` branch is repeated at 10 sites in `stream.py`, and `all_match`/`any_match`/`none_match` are three near-identical 12-line methods. It is also wrong for callable objects: `iscoroutinefunction()` is `False` for a class with an `async def __call__`, so `Stream.of([1,2,3]).map(AsyncDouble())` yields un-awaited coroutine objects with only a `RuntimeWarning` — no exception, silently corrupted output. | Bug fix and de-duplication in one: an `async def _maybe_await(fn, *args)` that calls first and checks `inspect.isawaitable(result)` handles async callable objects correctly and collapses all 10 sites. Note `flat_map` (`stream.py:110`) uses `iscoroutinefunction` to *reject* coroutines up front, so it needs handling separately rather than being folded into the helper. |

## Next

Real design/implementation work, but contained — mostly additive or scoped to
one area.

| Item | Why next |
|---|---|
| **Make `limit(n)` a real short-circuit** — `stream.py:179-186` only calls `iterable.aclose()` *after* receiving the element that exceeds the limit, so it pulls `n+1` elements from upstream: `Stream.of([1,2,3,4,5]).peek(seen.append).limit(2)` returns `[1, 2]` but leaves `seen == [1, 2, 3]`. | Java's `limit()` genuinely short-circuits; here every pipeline pays one extra `map`/`peek`/IO call, which matters when upstream is expensive or effectful. Fix is to check `size >= max_size` before pulling rather than after. Same area, needs deciding together: under `.parallel()`, whichever branch trips the limit `aclose()`s the *shared* source out from under the other three. |
| **Make `Stream` generic (`Stream[T]`)** — `BaseStream`/`Stream` are plain classes, so the `T`/`R` in their method signatures are unbound `TypeVar`s and element types are `Unknown` end to end. `ty` accepts `out: list[int] = await Stream.of([1,2,3]).map(lambda s: s.upper()).collect(to_list)` without complaint. | The callable *return* types in `type.py` are genuinely checked (a `str`-returning `Comparator` errors correctly), which makes the gap easy to miss — but nothing checks what flows *through* the pipeline, so half of `type.py` is decorative. Parameterizing (`map(Mapper[T, R]) -> Stream[R]`, `collect(Callable[[AsyncGenerator[T]], R]) -> R`) makes the existing aliases do real work and would have caught the `Comparator` class of bug statically. `StreamBuilder` is already `Generic[T]` but its `build()` returns a bare `Stream`, dropping the parameter — the seam is half-built already. |
| **Rename or re-scope `.parallel()` / `PROCESSES`** — currently just `asyncio` tasks racing over a shared generator (I/O-bound only, GIL-bound, no multiprocessing), but the naming implies real OS-thread parallelism like Java's `parallelStream()`. | Misleading naming is a correctness-of-understanding risk for callers. Decide: rename/docstring to set correct expectations, or build an actual multiprocessing-backed implementation. Either path is a breaking-rename candidate — track in README's pre-1.0 migration log per `CLAUDE.md`. |

## Later

Bigger, structural — needs explicit buy-in before starting since it changes a
core semantic.

| Item | Why later |
|---|---|
| **Decide mutable-builder vs. immutable-pipeline semantics** — every intermediate op (`filter`, `map`, `distinct`, etc.) does `self._chain.append(fn); return self`, mutating the instance rather than returning a new one. Diverges from Java's immutable stream semantics; a `Stream` reference can't be safely reused or forked once chaining starts. | Highest blast radius of any item here — affects every consumer of the chain-of-closures model described in `CLAUDE.md`. Needs an explicit decision (keep and document current behavior vs. change to return-new-instance-per-op) before any code moves, since it's a breaking change either way. |
| **`BaseStream.iterator()`** — expose a way to pull the composed stream as a plain Python iterator/async iterator without going through a collector. | README "Left to do". No urgent consumer; low priority until someone needs manual pull-based iteration outside `collect()`. |
| **`BaseStream.spliterator()`** — Java's parallel-decomposition iterator. | README "Left to do". Java-specific mechanism for splitting work across threads; snakestream's `ParallelStream` already parallelizes differently (racing `asyncio` tasks over a shared generator), so this may end up intentionally-skipped rather than implemented — needs a decision, not just an implementation. |
| **`BaseStream.unordered()`** — mark a stream as not order-dependent. | README "Left to do". Currently blocks `find_first()` from being distinguished from `find_any()` (see `stream.py`'s disabled `find_first`); implementing this unblocks that. |
| **`Stream.collect(supplier, accumulator, combiner)`** — Java's 3-arg mutable-reduction `collect()`, distinct from snakestream's existing single-arg `collect(collector)`. | README "Left to do". Snakestream's collector model (`collector.py`) already covers the common cases (`to_list`, `to_generator`); this variant adds Java-parity coverage but no currently-known consumer need. |
| **`Stream.forEachOrdered(action)`** — ordered variant of `for_each()`, meaningful once parallel streams can guarantee order. | README "Left to do". Depends on `unordered()`/ordering semantics being decided first, same as `find_first()`. |
| **`Stream.reduce(identity, accumulator, combiner)`** — 3-arg reduce with a combiner for parallel merging, distinct from the already-implemented 2-arg `reduce(identity, accumulator)`. | README "Left to do". The combiner only matters once parallel reduction is well-defined; low priority until `ParallelStream` semantics are more settled (see the `.parallel()`/`PROCESSES` naming item in Next). |
| **`Stream.reduce(accumulator)`** — 1-arg reduce with no identity, returning `Optional[T]`. | README "Left to do". Smaller lift than the 3-arg form since it can likely delegate to the existing 2-arg `reduce`, but still needs an `Optional`-style empty-stream return convention decided. |
| **`Stream.skip(n)`** — drop the first `n` elements. | README "Left to do". Straightforward, symmetric with the already-implemented `limit()`; no known blockers, just not yet built. |
| **`Stream.toArray()`** / **`Stream.toArray(generator)`** — materialize the stream into an array-like structure. | README "Left to do". Python doesn't have Java's array/generic-array-factory distinction, so this needs a decision on what the Pythonic equivalent even is (a `list`? then it's redundant with `collect(to_list)`) before implementing. |

## Done

- Added property-based tests with `hypothesis` for `map`, `filter`, `reduce`,
  `sorted`, `distinct` against a plain-Python reference oracle, covering
  edge cases hand-written tests miss (empty/single-element streams,
  duplicate keys, async callables).
- Added a `check_comparator_result_type()` runtime guard (`sort.py`) that
  raises `TypeError` if a user-supplied `Comparator` returns `bool` instead
  of `int`, used by `Stream._min_max()` (backing `min()`/`max()`) and both
  branches of `Stream.sorted()` (sync `cmp_to_key` path and the async
  `merge_sort`/`_merge` path). Closes a gap the earlier `Comparator`
  contract fix (below) didn't cover: Python's `bool` is a subclass of `int`,
  so a bool-returning comparator like `lambda x, y: x > y` type-checks fine
  under `ty`/mypy/pyright and previously degraded silently instead of
  erroring — for `min()` it could never signal "orders before" (always
  returning the first element), while `max()`'s behavior happened to be
  correct by coincidence. No static-typing trick can close this gap since
  it's structural to Python, not a `type.py` alias choice. Also fixed 18
  pre-existing tests across `tests/test_min.py`/`tests/test_max.py` that
  were passing bool comparators and only passed today via first-element
  luck (`min()`) or coincidence (`max()`); added regression tests asserting
  the `TypeError` for `min()`/`max()`/`sorted()`, sync and async. Tracked as
  **BREAKING** in README's migration log per `CLAUDE.md`.
- Fixed the `Comparator` type alias mismatch (`type.py:16`): kept a single
  Java-style 3-way *int* `Comparator` (matching `sorted()`'s existing usage
  and Java's own `Stream.min/max(Comparator)`), rather than splitting into
  two aliases, and fixed `Stream.min()`/`max()`/`_min_max()` (`stream.py`)
  to interpret the comparator's sign directly instead of treating it as a
  bool. This also fixed the tie-break bug for free: both `min()` and `max()`
  now keep the first of equal elements. Tracked as **BREAKING** in README's
  migration log per `CLAUDE.md` since bool-returning comparators passed to
  `min()`/`max()` now behave differently.
- Added an `install_smoke_test` CI job (`.github/workflows/check.yml`) that,
  for each of Python 3.10–3.14, creates a clean venv (`uv venv`, not
  `uv sync`), runs `pip install .` against the built package, and imports
  `snakestream` from outside the repo checkout — catching packaging
  mistakes that the source-tree `pytest` job wouldn't.
- Added static type checking to CI using `ty`, Astral's newer Rust-based
  type checker — chosen over `mypy`/`pyright` since it fit the existing
  `uv`/`ruff` toolchain and handled the codebase's `Awaitable`-union type
  aliases without issue. Fixed the 6 genuine type errors it surfaced
  (`BaseStream.on_close`'s return type, `ParallelStream`'s task-list
  typing, `StreamBuilder`'s unbound `TypeVar`, `Stream.collect`'s generic
  return type, and `Stream._min_max`'s sentinel-return typing), plus one
  scoped `ty: ignore` for a case the checker can't narrow via the
  runtime `iscoroutinefunction()` check in `Stream.sorted`. Gated to the
  3.14 matrix leg only, matching the coverage-gate precedent.
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
