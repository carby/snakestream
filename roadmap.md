# Roadmap

Now/Next/Later view of open code-quality and test-rigor items, generated from
the review-pass notes below. Completed items from that review remain in
**Done** for history.

## Now

Actively being picked up. Mostly low-risk and self-contained, but may
include a public-API item once there's a specific, near-term plan to do
the design work.

Ordered by dependency — items with no blockers first, items that depend on
an earlier item or on a Next-bucket decision last.

| # | Item | Why this position |
|---|---|---|
| 1 | **`BaseStream.iterator()`** — expose a way to pull the composed stream as a plain Python iterator/async iterator without going through a collector. | No blockers, no dependents; independent addition. |
| 2 | **`BaseStream.unordered()`** — mark a stream as not order-dependent. | No blockers itself, but unblocks #3 below and distinguishing `find_first()` from `find_any()` (see `stream.py`'s disabled `find_first`) — do this before its dependents. |
| 3 | **`Stream.forEachOrdered(action)`** — ordered variant of `for_each()`, meaningful once parallel streams can guarantee order. | Depends on #2 (`unordered()`/ordering semantics decided first). |
| 4 | **`Stream.collect(supplier, accumulator, combiner)`** — Java's 3-arg mutable-reduction `collect()`, distinct from snakestream's existing single-arg `collect(collector)`. | No blockers; independent Java-parity addition, no currently-known consumer need. |
| 5 | **`BaseStream.spliterator()`** — Java's parallel-decomposition iterator. | No hard blocker, but needs a decision first: Java-specific mechanism for splitting work across threads, and snakestream's `ParallelStream` already parallelizes differently (racing `asyncio` tasks over a shared generator), so this may end up intentionally-skipped rather than implemented. |
| 6 | **`Stream.toArray()`** / **`Stream.toArray(generator)`** — materialize the stream into an array-like structure. | No hard blocker, but needs a decision first: no Java array/generic-array-factory equivalent in Python, so what the Pythonic form even is (a `list`? redundant with `collect(to_list)`?) has to be settled before implementing. |
| 7 | **`Stream.reduce(identity, accumulator, combiner)`** — 3-arg reduce with a combiner for parallel merging, distinct from the already-implemented 2-arg `reduce(identity, accumulator)`. | Blocked on the **Next**-bucket `.parallel()`/`PROCESSES` semantics decision — the combiner only matters once parallel reduction is well-defined. Last in line. |

## Next

Real design/implementation work, but contained — mostly additive or scoped to
one area.

| Item | Why next |
|---|---|
| **Rename or re-scope `.parallel()` / `PROCESSES`** — currently just `asyncio` tasks racing over a shared generator (I/O-bound only, GIL-bound, no multiprocessing), but the naming implies real OS-thread parallelism like Java's `parallelStream()`. | Misleading naming is a correctness-of-understanding risk for callers. Decide: rename/docstring to set correct expectations, or build an actual multiprocessing-backed implementation. Either path is a breaking-rename candidate — track in README's pre-1.0 migration log per `CLAUDE.md`. |
| **Decide mutable-builder vs. immutable-pipeline semantics** — every intermediate op (`filter`, `map`, `distinct`, etc.) does `self._chain.append(fn); return self`, mutating the instance rather than returning a new one. Diverges from Java's immutable stream semantics; a `Stream` reference can't be safely reused or forked once chaining starts. | Highest blast radius of any item here — affects every consumer of the chain-of-closures model described in `CLAUDE.md`. Needs an explicit decision (keep and document current behavior vs. change to return-new-instance-per-op) before any code moves, since it's a breaking change either way. |

## Later

Bigger, structural — needs explicit buy-in before starting since it changes a
core semantic.

Nothing currently parked here — see **Now** for what moved up.

## Done

- Added `Stream.reduce(accumulator)` — the 1-arg, no-identity overload,
  returning `T | None` (`None` for an empty stream) rather than a wrapped
  `Optional[T]` type, matching the existing `find_any()`/`max()`/`min()`
  convention already used elsewhere in `stream.py`. Implemented as a single
  `reduce()` method carrying two `@overload` signatures (identity form and
  no-identity form) with one runtime body: a private `_UNSET` sentinel
  distinguishes "no identity given," in which case the first pulled element
  seeds the fold and an empty stream short-circuits to `None` before the
  accumulator is ever called; a single-element stream likewise returns that
  element without calling the accumulator. Delegates to the same
  `_maybe_await`-based accumulator dispatch the 2-arg form already used, so
  sync and async accumulators both work with no duplicated dispatch logic.
  Added a new `BinaryOperator` alias to `type.py` for the no-identity
  accumulator's `T, T -> T` shape, following the project's convention that
  composite/callable type shapes used in public signatures live in
  `type.py` rather than being written inline. Added 6 new tests in
  `tests/test_reduce.py` (empty stream, single-element stream, multi-element
  fold order, async-accumulator awaiting, a hypothesis property test against
  `functools.reduce`, and a regression check that the existing 2-arg form is
  unchanged). No changes to the existing `reduce(identity, accumulator)`
  behavior. See `openspec/changes/add-reduce-no-identity`.
- Added `Stream.skip(n)` — drops the first `n` elements pulled from upstream
  and yields the rest, symmetric with the already-implemented `limit(n)`.
  Implemented as `_SkipOp` (`stream.py`), mirroring `_LimitOp`'s
  `make_state()`/shared-state pattern so `ParallelStream._parallel()`'s
  existing generic `make_state()`-detection wires up correct parallel
  behavior (exactly `n` total elements dropped across all racing branches,
  not per-branch) with no `parallel_stream.py` changes needed. Unlike
  `limit()`, `skip()` has no short-circuit available — the first `n`
  elements must actually be pulled and discarded to advance upstream past
  them. Added `tests/test_skip.py` plus parallel-specific regression tests
  in `tests/test_parallel.py` (drops exactly `n` across branches, state
  fresh across separate streams). No public API change to existing methods.
  See `openspec/changes/add-stream-skip`.
- Made `Stream` generic (`Stream[T]`): `BaseStream`/`Stream`/`ParallelStream` were
  plain classes, so the `T`/`R` in their method signatures were unbound
  `TypeVar`s and element types were `Unknown` end to end — `ty` accepted
  `Stream.of([1,2,3]).map(lambda s: s.upper())` without complaint despite
  `int` having no `.upper()`. Fixed by making `BaseStream`/`Stream`/
  `ParallelStream` `Generic[T]`; `map()`/`flat_map()` now return `Stream[R]`
  via a narrowly-scoped `cast(Stream[R], self)` since the chain-of-closures
  model mutates and returns the same `self` rather than a new instance
  (deliberately not revisiting the separate mutable-builder-vs-immutable-
  pipeline decision below); type-preserving ops (`filter`, `distinct`,
  `peek`, `limit`, `sorted`) return `Stream[T]` directly; terminal ops are
  typed against the stream's bound `T`. Also fixed `type.py`'s `FlatMapper`
  alias, which hardcoded an unparameterized `Stream` instead of `Stream[R]`,
  and `StreamBuilder.build()`, which dropped its already-declared `T`
  instead of returning `Stream[T]`. Typing-only change, no runtime behavior
  differs. Added `tests/test_static_typing.py` plus `tests/typing/`
  fixtures that shell out to `ty check` to regression-test that the
  motivating bug is now caught and that valid generic usage still
  type-checks cleanly. See `openspec/changes/make-stream-generic`.
- Made `limit(n)` a real short-circuit: `_LimitOp.__call__` (`stream.py`) pulled
  an element from upstream *before* checking whether `max_size` had already
  been reached, so every `limit(n)` pipeline pulled `n+1` elements instead of
  `n` — e.g. `Stream.of([1,2,3,4,5]).peek(seen.append).limit(2)` returned
  `[1, 2]` but left `seen == [1, 2, 3]`. Fixed by checking the size before
  pulling rather than after, so upstream is closed without ever pulling an
  `n+1`th element. Under `.parallel()`, the shared `size_holder` in
  `ParallelStream._parallel`'s `state_map` already gave a global (not
  per-branch) limit guarantee; the fix changes *when* the shared source gets
  closed — whichever branch observes the shared count reaching `max_size`
  closes it before pulling further — and closure was made idempotent so a
  second racing branch closing (or pulling from) an already-closed shared
  source doesn't raise out of the task loop. No public API change. See
  `openspec/changes/archive/2026-08-12-fix-limit-short-circuit`.
- Replaced the repeated `if iscoroutinefunction(x): await x(...) else: x(...)`
  dispatch pattern (10 sites across `filter`, `map`, `sorted`'s comparator,
  `peek`, `reduce`, `for_each`, `min`/`max` via `_min_max`, and the
  `all_match`/`any_match`/`none_match` family) with a single
  `async def _maybe_await(fn, *args)` helper in a new
  `callable_dispatch.py`, which calls first and awaits the result only if
  `inspect.isawaitable(result)`. Fixes a real bug: `iscoroutinefunction()`
  is `False` for a class instance with an `async def __call__`, so passing
  such a callable object as a predicate/mapper/etc. previously produced an
  un-awaited coroutine flowing downstream as if it were a real value, with
  only a `RuntimeWarning` — no exception. `flat_map`'s existing
  `iscoroutinefunction()` check, which *rejects* coroutine-returning
  mappers up front, is a distinct pre-call classification and was left
  untouched. Also collapsed `all_match`/`any_match`/`none_match`'s three
  near-identical bodies into one shared `_match(predicate, short_circuit_on,
  default)` helper built on `_maybe_await`.

  `sorted()`'s comparator dispatch turned out not to fit the same
  call-then-await shape: its `iscoroutinefunction()` check picks between
  two different sort algorithms (`merge_sort`, which unconditionally
  awaits the comparator, vs. `list.sort()` with a sync `cmp_to_key`
  wrapper) rather than gating a single await. Fixed by moving `_merge`
  (`sort.py`) onto `_maybe_await` internally and always routing `sorted()`
  through `merge_sort` when a comparator is given, dropping the
  `cmp_to_key`/`list.sort()` branch entirely — this also closes the same
  async-callable-object gap for `sorted()`/`min()`/`max()`. Added
  regression tests (`tests/test_callable_dispatch.py`) covering
  `_maybe_await` directly (sync/async function, sync/async callable
  object) and each affected operation with an async-`__call__` callable
  object.
- Fixed two compounding bugs that made a second terminal operation on the
  same `Stream`/`ParallelStream` instance silently return wrong (usually
  empty) results instead of repeating the first run's behavior. First,
  `BaseStream._sequential()` (`base_stream.py`) was handed `self._chain`
  directly and called `pop(0)` on it, draining the caller's own chain list
  during `_compose()`; fixed by passing `self._chain[:]` (a copy) from
  `_compose()` instead — matching the copy `ParallelStream._parallel()`
  already made for its own branches, so both subclasses now honor the same
  non-destructive contract. Second, `distinct()`/`limit()` (`stream.py`)
  each built their `seen`/`size` state in the outer function that runs once
  per `.distinct()`/`.limit()` call, rather than in the closure that runs
  once per composition, so that state silently persisted across separate
  compositions of the same chain; fixed by replacing the two closures with
  small callable classes (`_DistinctOp`, `_LimitOp`) whose `__call__` takes
  an optional external state and falls back to fresh per-call state via
  their own `make_state()` when none is given — giving `Stream` (sequential)
  fresh state on every composition by default. For `ParallelStream`, where
  multiple racing branches must share one `seen`/`size` per composition to
  stay globally correct (matching Java's guarantee that parallel `distinct`/
  `limit` never silently degrade into a per-partition, unreconciled result,
  even though it costs more to coordinate — see
  `openspec/changes/fix-stream-rerun-state/design.md`), `_parallel()` now
  builds one state map per composition via each op's `make_state()` and
  passes the same map into every racing branch's `_sequential()` call.
  Added regression tests covering: chain length unaffected by composition,
  a second terminal op after the first, `distinct()`/`limit()` state not
  leaking across separate `Stream`/`ParallelStream` instances or across
  separate compositions of one instance, and parallel `distinct()`/`limit()`
  staying globally correct (no cross-branch duplicates, no over-`limit()`)
  across racing branches.
- Simplified `Stream.of()` (`stream.py`) from a four-way branch on dict vs.
  list vs. multiple positional args vs. kwargs down to two cases: a single
  positional arg passes straight through to `Stream()`'s existing source
  normalization, multiple args wrap into a list (one element each). The
  dict/list `isinstance` special-casing turned out to be dead complexity —
  tracing all 15 existing `test_of.py` cases showed it always produced the
  same call as the generic path, since `_normalize()` already re-spreads
  lists/dicts on its own. Also fixed `_normalize()` (`base_stream.py`) to
  treat `str`/`bytes` as scalar values, matching how Java's `Stream.of(T...)`
  treats `String`/`byte[]` atomically (byte arrays can't decompose via
  varargs since `T` can't bind to a primitive type), instead of the previous
  silent char-by-char/byte-by-byte spreading. Both changes are **BREAKING**
  and tracked in README's migration log per `CLAUDE.md`: `**kwargs` support
  is removed from `Stream.of()` entirely (no Java equivalent, undiscoverable,
  no real use case over `Stream.of(*some_dict.items())`), and
  `Stream.of("abc")`/`Stream.of(b"ab")` now yield one element instead of
  spreading.
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
