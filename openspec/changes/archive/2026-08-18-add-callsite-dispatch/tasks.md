> **Outcome: rejected at the task 3.2 benchmark gate.** Groups 1-3 ran; the
> single-site conversion regressed throughput 32-75% against a baseline whose
> inline dispatch measures as approximately free, so task 3.3 stopped the work
> as designed. Groups 4-10 were never started and are left unchecked
> deliberately. See `benchmark-findings.md`. Working tree reverted to HEAD.

## 1. Baseline

- [x] 1.1 Write a throwaway benchmark harness in the scratchpad matching the one `optimize-callable-dispatch` and `redesign-pipeline-sink-chain` both used: 20,000 elements, a chain of 8 `.map()` ops, best of 5 runs, reporting ns/element. Record the pre-change figure.
- [x] 1.2 Run `uv run pytest` and record the passing baseline plus the current coverage percentage, so any later drop is attributable.

## 2. Introduce `CallSite`

- [x] 2.1 Add `CallSite` to `callable_dispatch.py` per design Decision 1: `__slots__ = ("_fn", "_is_async", "_checked")`, `__init__` classifying via the existing `is_async_callable`, and an `async def __call__(self, *args)` returning the settled value.
- [x] 2.2 Give it a docstring stating the one caller rule — construct per callable per composition, never per operation — and nothing else; do not restate the dispatch logic in prose.
- [x] 2.3 Add direct unit tests to `tests/test_callable_dispatch.py` covering all four shapes against `CallSite` itself, independent of any stream operation: sync function, `async def` function, sync-`__call__` object, async-`__call__` object, plus the sync-signatured-callable-returning-a-coroutine safety net.
- [x] 2.4 Add a test asserting classification happens at most once: a callable that counts how often it is inspected, or equivalently that a `CallSite` reused across many elements produces correct results for both a sync and an async callable.

## 3. Prove the cost before converting everything

- [x] 3.1 Convert `_MapSink` in `stream.py` only: replace `self._mapper`/`self._is_async`/`self._checked` with `self._mapper = CallSite(mapper)` and the five-branch `accept` body with `await self.downstream.accept(await self._mapper(element))`. Drop the now-unneeded `cast(...)`.
- [x] 3.2 Re-run the benchmark from 1.1 against this single-site conversion and compare to the baseline. The chain is 8 `.map()` ops, so this isolates exactly the per-element coroutine-frame cost design flags as the one real risk.
- [x] 3.3 If the regression is material, stop and report the measured figures rather than continuing — the two-shape fallback in design Risks is a decision to surface, not to take unilaterally. Otherwise proceed.

## 4. Convert `stream.py`

- [ ] 4.1 Convert `_FilterSink` and `_PeekSink` the same way as `_MapSink`, each dropping two `__init__` lines and its `cast(...)`.
- [ ] 4.2 Convert the six terminal sites — `_collect_mutable` (accumulator), `reduce` (accumulator), `for_each` (consumer), `for_each_ordered` (consumer), `_min_max` (comparator), `_match` (predicate) — replacing each local `is_async`/`checked` pair with a local `CallSite` constructed in the same scope. Verify each construction site runs once per composition, not once per operation.
- [ ] 4.3 In `_min_max`, collapse the inner `async def compare` closure: with a `CallSite` it reduces to calling the site and then `check_comparator_result_type` on the settled value, with no `nonlocal` needed.
- [ ] 4.4 Leave `_maybe_await(supplier)` in `_collect_mutable` and `flat_map`'s `iscoroutinefunction` rejection check untouched, per design Non-Goals. Update the two comments at `stream.py:321-323` and `:359` that reference `_maybe_await` only if they became inaccurate.
- [ ] 4.5 Run `uv run pytest` and confirm the suite still passes before moving on.

## 5. Convert `collector.py` and delete `_classify_step`

- [ ] 5.1 Convert the six numeric collectors — `summing_int`, `summing_long`, `summing_double`, `averaging_int`, `averaging_long`, `averaging_double` — building the `CallSite` inside the returned closure body, not in the factory.
- [ ] 5.2 Convert `_extremum`'s comparator, `grouping_by`'s classifier and `partitioning_by`'s predicate.
- [ ] 5.3 Convert `reducing` to one `CallSite` per callable — mapper (only when the 3-arg overload supplies one) and binary operator — replacing both `_classify_step` calls and their tuple unpacking.
- [ ] 5.4 Convert `to_map` to three `CallSite`s — key mapper, value mapper, and merge function built only when the argument is not `None` — replacing all three `_classify_step` calls.
- [ ] 5.5 Delete `_classify_step` from `callable_dispatch.py` and remove its import from `collector.py`. Confirm no references remain.
- [ ] 5.6 Confirm `to_map` and `reducing` are under the mccabe gate without it by running `uv run ruff check .`.

## 6. Convert `sort.py`

- [ ] 6.1 Change `merge_sort(arr, comparator)` to build one `CallSite` and pass it down; change `_merge_sort` and `_merge` to take that site in place of the `comparator, state` pair, deleting the `state = [is_async, checked]` list and its explanatory comment.
- [ ] 6.2 Keep `check_comparator_result_type(sign)` applied to the settled value after the await, and keep the `sign <= 0` tie-break exactly as is so `sorted()` stability is unchanged.
- [ ] 6.3 Confirm `_SortedSink`'s comment at `stream.py:141-145` about always routing through `merge_sort` is still accurate.

## 7. Remove the canonical-shape comment

- [ ] 7.1 Delete the 40-line "Canonical shape for the 26 per-element call sites" comment block from `callable_dispatch.py` per design Decision 6.
- [ ] 7.2 Grep the repo for any other reference to the canonical shape, `_classify_step`, or the hand-copied pattern — including in `openspec/specs/`, prior change docs and `CLAUDE.md` — and update anything that now describes code that no longer exists. Do not edit archived changes.

## 8. Cover the new spec requirement

- [ ] 8.1 Add mixed sync/async tests to `tests/test_to_map.py` for the three `to_map` scenarios in the delta spec: sync key + async value, async key + sync value, and sync mappers + async merge function on a colliding key.
- [ ] 8.2 Add mixed sync/async tests to `tests/test_reducing.py` for the two `reducing` scenarios: sync mapper + async binary operator, and async mapper + sync binary operator.

## 9. Verify

- [ ] 9.1 Re-run the `callable-dispatch` spec's lifetime scenarios specifically — classification not leaking across compositions, and each parallel branch classifying independently — rather than trusting the suite total, per design Risks.
- [ ] 9.2 Run the full gate as CI does: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`, `uv run ty check src`, and `uv run pytest --cov-fail-under=98`.
- [ ] 9.3 Re-run the benchmark from 1.1 on the fully converted code and record the final ns/element figure alongside the baseline.
- [ ] 9.4 Confirm no test outside `tests/test_callable_dispatch.py`, `tests/test_to_map.py` and `tests/test_reducing.py` needed modification. If any did, that is a behavior change and must be explained rather than absorbed.

## 10. Document

- [ ] 10.1 Move the item from roadmap **Now** to **Done** with a writeup covering: the sites converted, `_classify_step`'s deletion, `sort.py`'s `state` list removal, the before/after benchmark figures, and a link to this change.
- [ ] 10.2 Confirm no README change is needed — no public API surface moved, and the migration log has nothing to record since there is no breaking change.
