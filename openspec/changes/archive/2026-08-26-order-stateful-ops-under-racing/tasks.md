## 1. Make the ordering fold reachable from execution.py

- [x] 1.1 Move the ordering fold out of `Stream._is_ordered()` into a
  module-level `is_ordered(chain: list[Op]) -> bool` in `src/snakestream/sink.py`,
  beside `Op` and `Ordering`; carry the existing docstring's reasoning (why it is
  folded rather than cached) with it.
- [x] 1.2 Reduce `Stream._is_ordered()` to a one-line delegation, keeping the
  method and its docstring's "private because Java exposes no ordering accessor"
  rationale. The four accessor scenarios in `stream-ordering`'s mode-switch
  requirement must still pass untouched.
- [x] 1.3 Add a `is_ordered_at(chain, i)` form (or an index argument) giving the
  fold over `chain[:i]`, which is what the split rule needs.
- [x] 1.4 Run `uv run pytest tests/test_unordered.py tests/test_for_each_ordered.py`
  and confirm no behaviour changed; this group is pure relocation.

## 2. Declare order-sensitivity on the Op protocol

- [x] 2.1 Add an `order_sensitive: ClassVar[bool] = False` declaration to `Op` in
  `src/snakestream/sink.py`, documented alongside `ordering` and
  `make_shared_state()` in the class docstring: it says whether this operation's
  *result* depends on an element's position, where `ordering` says what the
  operation does *to* the characteristic.
- [x] 2.2 Set it `True` on `_LimitOp`, `_SkipOp` and `_DistinctOp` in
  `src/snakestream/ops.py`. `_SortedOp` needs no flag — it already declares
  `Ordering.SET`, which is the first clause of the split rule (design Decision 2).
- [x] 2.3 Extend `tests/test_op_protocol.py` to pin the default and the three
  overrides, and that no other op declares it.

## 3. The split rule

- [x] 3.1 Implement the split-point search in `src/snakestream/execution.py`: the
  first index `i` whose op either declares `Ordering.SET` or is
  `order_sensitive` with the fold over `chain[:i]` reporting ordered. Return
  `None` when there is none.
- [x] 3.2 Unit-test the search directly against representative chains, including
  the two cases design Decision 2 turns on: `.unordered().sorted()` splits at the
  sort, and `.unordered().sorted().limit(3)` splits at the sort rather than at the
  limit.
- [x] 3.3 Confirm that a chain with no split point returns `None` for every
  purely order-preserving chain and for every stateful op sitting at an unordered
  position.

## 4. Group-yielding branches

- [x] 4.1 Add the group-yielding variant of `stream_through()` that yields
  `(index, outputs)` per source element instead of yielding elements one at a
  time, taking the index from the element it just pulled and using the existing
  `GeneratorBridgeSink` buffer flush as the group boundary.
- [x] 4.2 Flush anything emitted at `end()` as a final group ordered after every
  real one, so a head op that emits on `end()` is not lost.
- [x] 4.3 Teach `_guarded()` to assign the source index under the lock and hand it
  on with the element.
- [x] 4.4 Verify the plain `stream_through()` path is untouched and still used by
  `Sequential.elements()` and by every branch when there is no split point.

## 5. The reorder merge

- [x] 5.1 In `race_through()`, when a split point exists, run the head ops in the
  branches and hold arriving groups in a dict keyed by index, releasing while the
  next expected index is present.
- [x] 5.2 Drive the tail ops as one sequential sink chain over the released
  stream, exposing the result as the generator `Racing.elements()` returns —
  leaving `Racing.value()` on the inherited generic form and `Executor` unchanged.
- [x] 5.3 Build the shared state map from the whole chain as today; head ops still
  share state across branches, tail ops are built once.
- [x] 5.4 Confirm `race_through()` takes today's code path exactly when there is
  no split point.

## 6. Bounded read-ahead

- [x] 6.1 Add the window object (last released index plus an `asyncio.Event`)
  shared between the merge and `_guarded()`, and the module-level `W` constant —
  not exported, per design Decision 4.
- [x] 6.2 In `_guarded()`, await the window *before* competing for the lock and
  re-check after acquiring it; never wait while holding the lock.
- [x] 6.3 Have the merge bump the released index and set the event on each
  release.
- [x] 6.4 Test: a source far longer than `W` whose first element is far slower
  than the rest completes, and the number of elements pulled ahead of the first
  release stays within the window.
- [x] 6.5 Test: closing the composed generator while a branch is blocked on the
  window does not hang — `aclose()` returns and no task is left uncancelled.

## 7. Cancellation across the barrier

- [x] 7.1 Confirm cancellation raised by a tail `limit()` reaches the upstream
  pull: the driving loop closes the merged generator, `race_through()`'s `finally`
  cancels the branches, and `_guarded()`'s `finally` closes the shared source.
- [x] 7.2 Test: an ordered racing `.limit(n)` over an infinite source yields
  exactly `n` elements in encounter order and terminates.
- [x] 7.3 Test: the shared source is closed exactly once, and a second branch
  pulling from or closing it after another branch closed it still ends cleanly —
  the existing `pipeline-composition` scenarios must keep passing with a barrier
  in play.

## 8. The four operations, behaviourally

- [x] 8.1 `tests/test_limit.py`: the roadmap's reproduction — `range(12)`, a map
  slow for the first five, `.parallel().limit(5)` yields `[0, 1, 2, 3, 4]`.
- [x] 8.2 `tests/test_skip.py`: the same source with `.skip(5)` drops `0..4`.
- [x] 8.3 `tests/test_sorted.py`: an **async** source yielding `12..1` with
  `.parallel().sorted(asc)` yields `[1..12]`; add the list-source form too, and
  make it fail for the right reason by asserting the ordering requirement was
  honoured rather than that one branch happened to take everything.
- [x] 8.4 `tests/test_distinct.py`: equal-but-distinguishable objects — the
  survivor is the earliest in encounter order.
- [x] 8.5 For each of the four, the mirror case: with `.unordered()` queued
  before the op, the order-blind result is produced and no ordering machinery
  runs.
- [x] 8.6 Each of the four with the op queued *before* `.parallel()`, confirming
  the executor governs the whole pipeline.

## 9. Repay the test debt (a condition of this change, not a follow-up)

- [x] 9.1 Restate the four `sorted()`-restores tests in `tests/test_unordered.py`
  behaviourally and delete the section comment's "restate them behaviourally once
  ordered `sorted()` under RACING lands" note.
- [x] 9.2 Repair
  `tests/test_for_each_ordered.py::test_sorted_after_unordered_restores_the_for_each_ordered_guarantee`
  so it fails when `sorted()` stops restoring encounter order.
- [x] 9.3 Add a `test_for_each_ordered.py` test that notices when the
  `unordered()` relaxation of `for_each_ordered()` stops happening — the roadmap
  records that rule as pinned only inside `test_unordered.py`.
- [x] 9.4 Re-run the three mutation inversions (`_is_ordered()` always `True`,
  always `False`, `_SortedOp.ordering` = `PRESERVE`) and confirm each is now
  caught by at least one behavioural test. Record the resulting counts in the
  change's notes the way the roadmap's table does.

## 10. Measure

- [x] 10.1 Benchmark the unordered racing path before and after; a measurable
  per-element regression there is a blocker, not a footnote.
- [x] 10.2 Benchmark the ordered racing path against the sequential path on
  `.map(slow).limit(5)` to show the concurrency this change is for is actually
  kept, and record the figures.
- [x] 10.3 Pick `W` from the read-ahead/latency trade-off on those benchmarks and
  record the figures beside the constant, the way `Sequential.value()`'s docstring
  records its own.

## 11. Specs and docs

- [x] 11.1 Update `openspec/specs/stream-execution-model/spec.md`'s stale
  `find_first()` wording via this change's delta — the code has been
  unconditional since `make-ordering-a-chain-characteristic` and
  `tests/test_find_first.py` agrees.
- [x] 11.2 Update `CLAUDE.md`'s execution section: the primitive list, and the
  unconditional "Racing does not preserve ordering" claim, which becomes
  conditional.
- [x] 11.3 Update `README.md` wherever it repeats that claim.
- [x] 11.4 Move the roadmap's **Now** item to **Done** with what was decided and
  why, and record the deferred follow-up: `find_first()`/`for_each_ordered()`
  can now be collapsed onto the barrier, and `W` could be exported if a concrete
  report asks for it.

## 12. Gates

- [x] 12.1 `uv run pytest` green, and `uv run pytest --cov-fail-under=98` clears.
- [x] 12.2 `uv run ruff check .`, `uv run ruff format --check .` and
  `uv run ty check src` all clean.
- [x] 12.3 `openspec validate --change order-stateful-ops-under-racing --strict`
  passes.
