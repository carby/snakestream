## Why

`add-free-threaded-ci-leg` established the substrate. This change spends it.

Three roadmap items have been blocked behind one another for months — real
parallelism, `spliterator()`, and live combiners — and the block was always the
same thing: no way to run user callables on more than one core. Free-threading
removes it. Measured against the **real library**, not a synthetic harness:
materialising contiguous batches and running the actual chain over each in a
worker thread gives **2.37x** on a sync mapper and **2.36x** on an async one, at
4 workers, with output identical to sequential and encounter order preserved
through `flat_map`'s cardinality change.

The second reason is subtraction. The racing executor destroys encounter order
at its merge and then rebuilds it, and that rebuilding is the most intricate
machinery in the package: `_Window`, `_guarded`'s windowed branch,
`_group_through`, `_releasable`, `_release_in_order`, `_run_ordered_tail`,
`_racing_branches` and `_race_through` itself — **400 of `execution.py`'s 676
lines**. Contiguous batches never destroy encounter order, so none of it is
needed. This change deletes it.

## What Changes

- **NEW public API**: `Stream.spliterator()` returning a `Spliterator[T]` with
  Java's method surface — `try_advance`, `try_split`, `estimate_size`,
  `characteristics`, `for_each_remaining`. README's struck-through row becomes
  an implemented one. It is load-bearing rather than decorative: the new
  executor is built on it, which is what makes it a real implementation of
  Java's contract rather than a shim added for the parity table.
- **NEW executor**: `_ForkJoin`, bound as `FORK_JOIN`. `.parallel()` now
  produces it. It decomposes the source into contiguous batches, runs each
  batch's chain in a worker thread on that thread's own event loop, and
  concatenates in batch order.
- **BREAKING**: `RACING` and `_Racing` are removed. `.parallel()`'s *observable
  contract* is unchanged for an ordered pipeline — same elements, same
  encounter order, same short-circuiting — but the mechanism underneath it is
  entirely different, and anything importing `RACING` from
  `snakestream.execution` breaks loudly.
- **BREAKING (found during implementation)**: `unordered()` no longer relaxes
  *delivery* order under `.parallel()`. It still buys the one thing fork/join
  cannot deliver for free — a stateful op (`limit`/`skip`/`distinct`) runs
  inside the parallel batches, sharing locked state, instead of a single
  global-view pass — but a terminal now always receives elements in encounter
  order, `unordered()` or not, since contiguous batches never scramble order
  and recovering the old completion-order delivery would mean reintroducing a
  real merge. See design.md, decision 9.
- **BREAKING**: `PROCESSES` is renamed `WORKERS`. It counts worker threads and
  never counted processes; the old name was retained only against the
  possibility of a process-pool implementation, which this change settles by
  making threads the answer. Loud, with `ImportError`.
- **Deleted**: the whole reorder-barrier apparatus listed above. Three
  properties replace it, each for free:
  - `asyncio.gather` preserves argument order, so order *within* a batch needs
    no buffer;
  - batches are contiguous and consumed in order, so order *across* batches
    needs no index tagging;
  - batch size bounds in-flight work, so `_IN_FLIGHT_PER_WORKER`, `_in_flight()`
    and `_Window` collapse into one number that was already there.
- **Retained**: `split_point()`. A stateful op (`sorted`, `distinct`, `limit`,
  `skip`) still cannot run independently per batch, so it still splits the
  chain — but the barrier becomes trivial, because batches already arrive in
  order. The decision logic survives; the machinery that acted on it does not.
- README's **About `.parallel()`** section is rewritten. It currently states
  that real parallelism is blocked on pickling, which this change makes false.

## Capabilities

### New Capabilities

- `stream-spliterator`: the public `Spliterator` contract — decomposition,
  traversal, size estimation and characteristics — and `Stream.spliterator()`.

### Modified Capabilities

- `racing-encounter-order`: every requirement is stated in terms of the racing
  merge and its reorder barrier. The *guarantees* survive verbatim — an ordered
  parallel pipeline still delivers in encounter order, `unordered()` is still
  the escape hatch, the read-ahead bound is still not public — but what
  provides them changes completely. See `design.md`, decision 5, on why the
  capability keeps its directory name despite now describing fork/join.
- `stream-execution-model`: the set of executors changes, and with it the claim
  that a parallel executor cannot fuse a terminal onto one chain.
- `pipeline-composition`: the requirement "Parallel branches serialize pulls
  from the shared upstream source" describes a mechanism that ceases to exist.
  The correctness requirements around parallel `distinct`/`limit`/`skip` are
  restated against batches rather than branches.

**Deliberately not modified — the ~18 other specs mentioning RACING.** Checked
individually: they say things like "on an ordered `RACING` pipeline this
collector takes the delivery barrier", which remains true. They describe
*behaviour under parallel execution*, and this change preserves that behaviour
exactly. Their surviving mentions of the executor's name are corrected as prose
in the same commit, but no requirement moves. See `design.md`, decision 6.

## Impact

- `src/snakestream/execution.py` — ~400 lines deleted, `_ForkJoin` added
- `src/snakestream/spliterator.py` — new module
- `src/snakestream/stream.py` — `spliterator()`; `.parallel()` binds `FORK_JOIN`
- `src/snakestream/ordering.py` — `split_point()` retained, its contract narrowed
- `src/snakestream/ops.py` — `LimitOp`/`SkipOp`/`DistinctOp`'s shared state
  (`Box`/`set`) replaced with `threading.Lock`-guarded equivalents
  (`_GuardedCounter`, `_GuardedSet`); see design.md, decision 8, added during
  implementation once fork/join's real OS threads made the existing
  check-then-mutate no longer atomic for free
- `README.md` — the `.parallel()` section, two parity rows, Migration entries
- `CLAUDE.md` — the execution architecture section, substantially
- `roadmap.md` — two **Later** items resolved, one unblocked
