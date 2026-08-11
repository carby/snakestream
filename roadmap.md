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
| **Add property-based tests with `hypothesis`** for `map`, `filter`, `reduce`, `sorted`, `distinct` | Cheaply catches edge cases hand-written tests miss (empty inputs, duplicate keys, non-comparable types, single-element streams). Needs some setup but no API changes. |
| **Simplify `Stream.of()`** — currently branches on dict vs. list vs. multiple positional args vs. kwargs into one `source` list (`stream.py:36-59`); unclear what `Stream.of(1, [2, 3])` or `Stream.of(a=1, b=2)` produce without tracing the logic. | Worth splitting into narrower, clearer construction paths. Touches public API — needs a design decision on the replacement shape before implementation; track any resulting rename in README's pre-1.0 migration log per `CLAUDE.md`. |
| **Split the `Comparator` type alias — it currently means two incompatible things.** `type.py:16` declares `Comparator = Callable[[T, T], bool \| Awaitable[bool]]`, but `sorted()` needs a Java-style 3-way *int* comparator (`sort.py:17` does `await comparator(...) <= 0`; `stream.py:136` does `cmp_to_key(comparator)`) while `min()`/`max()` need a *bool* one (`stream.py:250` does `if comparator(n, found)`, and `min()` negates it via `not comparator(x, y)` at `stream.py:229,235`). | Both directions fail **silently**, with no exception and no `ty` error (the alias itself is wrong, so nothing can catch it): a 3-way comparator gives `max([3,1,2]) -> 2` (should be `3`) and `min([3,1,2]) -> 3` (should be `1`); a bool comparator gives `sorted([3,1,2]) -> [3,1,2]`, silently unsorted. Pick one contract, split the alias (e.g. `Comparator` vs. `BiPredicate`), and track the resulting signature change in README's pre-1.0 migration log per `CLAUDE.md`. Secondary, same area: even with a correct bool comparator, `not comparator(x, y)` is true on ties, so `min()` returns the *last* of equal elements while `max()` returns the first. |
| **Stop `_sequential()` from destroying `self._chain`** — `base_stream.py:38,40` calls `pop(0)` on the caller's live list, so `_compose()` empties the chain and a second terminal op on the same stream yields nothing (`collect -> [2,4,6]`, then `collect -> []`). `ParallelStream._parallel` already passes a copy (`intermediaries[:]`, `parallel_stream.py:21`), so the same `_compose()` contract behaves differently per subclass. | One-line fix (`intermediaries[:]`, or replace the recursion with an iterative loop and also drop the O(len(chain)) stack frames). Adjacent to the mutable-builder item in **Later** but independent of it: that one is about intermediate ops doing `return self`, this is unintended mutation inside compose, and it can be fixed without pre-deciding the larger semantic question. |

## Next

Real design/implementation work, but contained — mostly additive or scoped to
one area.

| Item | Why next |
|---|---|
| **Make `limit(n)` a real short-circuit** — `stream.py:179-186` only calls `iterable.aclose()` *after* receiving the element that exceeds the limit, so it pulls `n+1` elements from upstream: `Stream.of([1,2,3,4,5]).peek(seen.append).limit(2)` returns `[1, 2]` but leaves `seen == [1, 2, 3]`. | Java's `limit()` genuinely short-circuits; here every pipeline pays one extra `map`/`peek`/IO call, which matters when upstream is expensive or effectful. Fix is to check `size >= max_size` before pulling rather than after. Same area, needs deciding together: under `.parallel()`, whichever branch trips the limit `aclose()`s the *shared* source out from under the other three. |
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
