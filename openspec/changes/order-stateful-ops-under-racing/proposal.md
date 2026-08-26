## Why

Four intermediate operations give **wrong answers** on an ordered pipeline under
`RACING` — not slower answers, wrong ones. `_LimitSink`/`_SkipSink` share one
counter across racing branches and `_DistinctSink` shares one set, so all three
implement Java's *unordered* behaviour unconditionally; `_SortedOp` is a
`StatelessOp`, so each branch buffers and sorts its own subset and the merged
output is not sorted at all. Java defaults to the ordered path and takes the
cheap one only when `ORDERED` is absent. Measured 2026-08-26, all reproducible:

| Op | Ordered `.parallel()` result | Java / sequential |
|---|---|---|
| `.map(slow).limit(5)` over `range(12)`, first five slow | `[0, 1, 2, 3, 5]` | `[0, 1, 2, 3, 4]` |
| `.map(slow).skip(5)`, same source | keeps `4`, drops `5` | drops `0..4` |
| `.sorted(asc)` over `range(12, 0, -1)`, async source | `[4, 2, 3, 1, 8, 6, 7, 12, 5, 10, 11, 9]` | `[1, 2, ..., 12]` |

Why now: `make-ordering-a-chain-characteristic` made `_is_ordered()` a reliable
*positional* answer, which is the thing an op needs to branch on and could not
have before. And the defect is now blocking test rigor as well as correctness —
a sort under `RACING` is currently indistinguishable from an unordered one, so
nothing behavioural in the suite notices when `sorted()` stops restoring
encounter order (verified by mutation, 2026-08-26). Fixing the ops by forcing
the whole pipeline sequential would fix the bug in a way that permanently
forecloses ever observing that rule behaviourally.

All three bugs are one bug seen from three angles: **a stateful op's decision
depends on a global position its branch cannot see.** Encounter order is
knowable in exactly one place — inside `_guarded()`, under the shared lock, the
last point at which pull order still *is* encounter order — and destroyed in
exactly one place, the `FIRST_COMPLETED` merge in `race_through()`.

## What Changes

- **New: a windowed reorder barrier in `execution.py`.** `_guarded()` tags each
  element with the source index it assigns under the lock. The chain is split at
  the first order-sensitive stateful op whose position is ordered: everything
  upstream races across branches as today, a reorder buffer at the merge
  releases elements in index order, and everything downstream of the barrier
  runs as one sequential sink chain over that ordered stream.
- **Read-ahead is bounded, not unbounded.** `_guarded()` refuses to pull an
  index more than a fixed window `W` ahead of the last released index. The
  refusal sits in the same place the index is assigned, which is also the only
  place a pull happens — so the bound costs no new synchronisation point. This
  is the analogue of the leaf partitioning Java's fork-join bounds itself with.
  Head-of-line blocking remains, as it must: it is inherent to ordering.
- **`sorted()`, `limit()`, `skip()` and `distinct()` become correct under an
  ordered `RACING` pipeline** — the first `n` in encounter order, the first
  `n` dropped in encounter order, first-duplicate-wins, and a real sort — while
  still racing every op upstream of the barrier. `.map(fetch).limit(5)` keeps
  its concurrency on the `map`, which is the pipeline shape `RACING` exists for.
- **`unordered()` becomes a genuine performance lever.** On an unordered
  pipeline no barrier is inserted and today's cheap shared-state path runs
  unchanged, which is exactly Java's `StreamOpFlag` story. Today the
  characteristic is consulted by one caller and has no cost consequence.
- **Test debt on the sort is repaid in the same change** (the roadmap makes it
  a condition of this fix, not a follow-up): the four `sorted()`-restores tests
  in `tests/test_unordered.py` are restated behaviourally and their "restate
  once (a) lands" notes deleted; the weak
  `test_sorted_after_unordered_restores_the_for_each_ordered_guarantee` in
  `tests/test_for_each_ordered.py` is repaired; the three ordering inversions
  are re-run to confirm each is now caught behaviourally, including the
  currently-unpinned `unordered()` relaxation of `for_each_ordered()`.
- **Out of scope, deliberately:** `find_first()` and `for_each_ordered()` keep
  naming `SEQUENTIAL`. The barrier makes racing them possible and collapses four
  special cases into one mechanism, but that is a separate change; a roadmap
  note records it. This change does correct the stale `stream-execution-model`
  wording that says `find_first()` branches on ordering, which `stream.py:377`
  has done unconditionally since `make-ordering-a-chain-characteristic`.
- **Not BREAKING.** No public signature changes. Results change only where they
  were wrong: an ordered `RACING` pipeline containing one of the four ops.

## Capabilities

### New Capabilities
- `racing-encounter-order`: the reorder barrier — index assignment at the
  shared source, where the chain is split, in-order release, the bounded
  read-ahead window, and what `sorted()`/`limit()`/`skip()`/`distinct()`
  guarantee on an ordered pipeline under the racing executor versus an
  unordered one.

### Modified Capabilities
- `pipeline-composition`: "Parallel distinct() and limit() remain globally
  correct across branches" and "Parallel skip() remains globally correct across
  branches" currently state the unordered semantics as the unconditional
  contract ("first `n` means the first `n` elements pulled across all branches
  in whatever order the race resolves them"). Both become conditional on the
  pipeline being unordered at that op's position.
- `stream-ordering`: "sorted() restores encounter order downstream" — its
  scenarios stop asserting on the internal accessor and are restated
  behaviourally, and the paragraph explaining why they could not be is removed.
  The mode-switch requirement's accessor assertions are structural and stay.
- `stream-execution-model`: correct the `find_first()` wording to the
  unconditional rule the code implements; note that the racing executor's
  element-producing operation may insert a barrier without that being a second
  executor.

## Impact

- `src/snakestream/execution.py` — `_guarded()` (index tagging, window
  backpressure), `race_through()` (chain split, reorder release), the new
  barrier primitive. This is where nearly all of the change lands.
- `src/snakestream/ops.py` — `_SortedOp`/`_LimitOp`/`_SkipOp`/`_DistinctOp`
  declare order-sensitivity so the split point can be found; sink bodies are
  otherwise unchanged, since downstream of the barrier they see an ordered
  stream and the existing sequential logic is already right.
- `src/snakestream/sink.py` — the `Op` protocol gains the order-sensitivity
  declaration alongside `ordering` and `make_shared_state()`.
- `src/snakestream/stream.py` — likely unchanged; the barrier is an execution
  concern. `_is_ordered()` gains callers inside `execution.py`, which means the
  chain fold must be reachable from there.
- Tests: `test_unordered.py`, `test_for_each_ordered.py`, `test_sorted.py`,
  `test_limit.py`, `test_skip.py`, `test_distinct.py`, `test_parallel.py`,
  `test_compose.py`, `test_execution_model.py`.
- Docs: `CLAUDE.md`'s execution section (the primitive list and the
  "Racing does not preserve ordering" claim, now conditional), `README.md` if
  it repeats that claim, and `roadmap.md` (**Now** item closed to **Done**,
  with the terminals follow-up recorded).
- Risk to watch: memory under the window, cancellation crossing the barrier
  (`limit`'s `cancellation_requested()` now sits downstream of the merge and
  must still stop the upstream pull), and per-element cost on the unordered
  path, which must stay exactly as it is today.
