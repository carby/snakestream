## 1. Seed the ordering fold

- [x] 1.1 Give `is_ordered()` in `sink.py` an `initial: bool = True` parameter that seeds the fold instead of starting from `True`, and document why a suffix re-entry needs it.
- [x] 1.2 Add a unit test that `is_ordered(chain, initial=False)` reports unordered for a chain of only PRESERVE ops, and ordered once a `sorted()` op SETs it.

## 2. Carry the ordering demand through the executor protocol

- [x] 2.1 Add `observes_order: bool` to `Executor.elements()` and `Executor.value()` in `execution.py`, updating the abstract signatures and the generic `value()` to pass it through to `elements()`.
- [x] 2.2 Accept and ignore it in `Sequential.elements()`/`Sequential.value()`, with a comment saying the sequential executor is ordered by construction.
- [x] 2.3 Pass it from `Racing.elements()` into `race_through()`.
- [x] 2.4 Add `observes_order: bool` and `ordered_in: bool = True` parameters to `race_through()`.

## 3. The terminal barrier

- [x] 3.1 Give `_split_point()` the two new parameters and a final clause: with no op-based split, return `len(chain)` when `observes_order and is_ordered(chain, initial=ordered_in)`; seed the existing `is_ordered(chain, i)` call with `ordered_in` too. Update its docstring to describe both callers.
- [x] 3.2 Verify `race_through()`'s existing split branch handles `split == len(chain)` — head is the whole chain, tail is empty — and adjust `_run_ordered_tail()` to yield the reordered stream directly for an empty tail.

## 4. Replace `_resume_point()`

- [x] 4.1 Delete `_resume_point()`.
- [x] 4.2 Rewrite `_run_ordered_tail()`: run `tail[0]` alone through `stream_through()`, then hand `tail[1:]` to `race_through()` with `observes_order` and with `ordered_in` set to the ordering state after `tail[0]`. Yield directly when the tail has fewer than two ops. Rewrite the docstring around the new rule.
- [x] 4.3 Update `race_through()`'s and the module docstrings in `execution.py` to describe the two barrier callers and the new tail rule.

## 5. Terminals declare whether they observe encounter order

- [x] 5.1 Add an `observes_order: bool` parameter to `Stream._evaluate()` and pass it to the executor.
- [x] 5.2 Have `count()`, `for_each()`, `find_any()`, `max()`, `min()`, `all_match()`, `any_match()` and `none_match()` declare `False`.
- [x] 5.3 Have `reduce()`, `to_array()` and `_collect_mutable()` declare `True`.
- [x] 5.4 Have `collect(collector)` derive it: `Characteristics.UNORDERED not in collector.characteristics`.
- [x] 5.5 Have `iterator()` declare `True`, so `collect(to_generator)` and `Stream.concat()` follow through the same call.
- [x] 5.6 Leave `find_first()` and `for_each_ordered()`'s executor selection exactly as it is; give each the declaration that matches what it already does.

## 6. Tests for the new behaviour

- [x] 6.1 Ordered racing `map`/`filter` pipelines collect in encounter order and equal the sequential result, for sync and async sources.
- [x] 6.2 `reduce()` with a non-commutative accumulator matches the sequential fold under `.parallel()`.
- [x] 6.3 `to_array()`, `collect(to_generator)` and `iterator()` deliver in encounter order on an ordered racing stream.
- [x] 6.4 `to_set()` and any collector declaring `UNORDERED` take the order-blind path; an otherwise identical collector without the declaration delivers in order.
- [x] 6.5 `.unordered()` before the terminal removes the delivery barrier; `.unordered()` after an order-sensitive op leaves that op's selection intact while clearing delivery order.
- [x] 6.6 Order-blind terminals (`count`, `for_each`, `any_match`, `find_any`) engage no barrier and are unchanged.
- [x] 6.7 Delivery ordering does not serialize: an ordered racing pipeline over a sleeping mapper completes in substantially less wall time than the sequential one.
- [x] 6.8 The resumed suffix races: `.parallel().limit(8).map(slow)` produces its eight elements concurrently, in encounter order.
- [x] 6.9 `.parallel().sorted(asc).map(f).collect(to_list())` is sorted; `.parallel().limit(20).map(f).sorted(asc)` is sorted; `.parallel().sorted(asc).unordered().map(f)` is not.
- [x] 6.10 Under a delivery barrier: a closeable source is closed exactly as many times as without one, an error in a mapper propagates without hanging, and read-ahead over a large source with one slow head element stays within the window.
- [x] 6.11 `is_parallel()` still reports `True` under both barrier shapes.

## 7. Documentation

- [x] 7.1 README: add the behaviour break to the migration log, and update the ordering prose to say an ordered racing pipeline delivers in encounter order and that `unordered()` is the opt-out.
- [x] 7.2 `CLAUDE.md`: rewrite the "racing destroys encounter order" framing in the ordering-barrier section to cover the delivery barrier and the new tail rule, and drop the `_resume_point()` description.
- [x] 7.3 Docstrings: `unordered()`, `parallel()`/`sequential()` and the collector `characteristics` docs mention that `UNORDERED` is now read.

## 8. Measurement

- [x] 8.1 Benchmark ordered vs `.unordered()` racing delivery on a chain with no order-sensitive op (per-element cost and wall time), and record the figures in `_READ_AHEAD`'s or `race_through()`'s docstring alongside the existing ones.
- [x] 8.2 Benchmark `.limit(n).map(slow)` before and after, showing the suffix regains concurrency.
- [x] 8.3 Report both sets of figures. If the ordered default regresses further than the concurrency it preserves justifies, stop and surface it rather than absorbing it.

## 9. Validation

- [x] 9.1 `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src`.
- [x] 9.2 `uv run pytest --cov-fail-under=98`.
- [x] 9.3 `openspec validate order-racing-delivery --strict`.
