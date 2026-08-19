## 1. Baseline

- [x] 1.1 Record the pre-change baseline: `uv run pytest` test count and coverage percentage, so the post-change run can be compared exactly.
- [x] 1.2 Write the benchmark harness to the scratchpad (not the repo), matching the one `redesign-pipeline-sink-chain` and `collapse-op-classes` used: Python 3.14.5, 20,000 elements, chain of 8 `.map()` ops, best of 5. Add a second scenario driving a non-short-circuiting terminal (`count()`) rather than `collect(to_list)`, since that is the path this change alters. Record baseline ns/element for both.

## 2. The drive loop

- [x] 2.1 Add `_drive_to_sequential(terminal)` to `BaseStream`: `_check_not_consumed()`, link `self._chain` onto `terminal` via the existing `_sequential()` helper, wrap `self._stream` in `_maybe_aclosing`, `begin({})` / push-and-check-cancellation loop / `end()`, return `terminal.result()`.
- [x] 2.2 Add `_drive_to(terminal)` to `BaseStream` delegating to `_drive_to_sequential(terminal)`.
- [x] 2.3 Type both against `TerminalSink[Any]`; confirm `uv run ty check src` is clean before any terminal uses them.

## 3. terminals.py

- [x] 3.1 Create `src/snakestream/terminals.py` and move `_UNSET` into it from `stream.py`; re-import it in `stream.py` (`reduce()`'s overload dispatch still needs it). Confirm no import cycle: `terminals.py` imports only `sink.py`, `callable_dispatch.py`, `sort.py`, `type.py`.
- [x] 3.2 `_CountSink`: container is a `Counter`, `_finish` returns `.value`.
- [x] 3.3 `_ForEachSink(consumer)`: per-element dispatch copied verbatim from `Stream.for_each` with `_is_async`/`_checked` as instance attributes (per design Goals — do not abstract the dispatch shape); `_finish` returns `None`.
- [x] 3.4 `_ReduceSink(identity, accumulator)`: `_create_container` returns `identity` (possibly `_UNSET`); `accept` seeds from the first element when the container is `_UNSET`, otherwise folds; `_finish` maps a still-`_UNSET` container to `None`.
- [x] 3.5 `_MinMaxSink(comparator, asc)`: `_UNSET`-seeded container, comparison body and `check_comparator_result_type` call moved verbatim from `Stream._min_max`, `_finish` maps `_UNSET` to `None`.
- [x] 3.6 `_MutableReductionSink(container, accumulator)`: takes the already-awaited container; `_create_container` returns it; `accept` applies the accumulator with the standard dispatch shape.
- [x] 3.7 `_FindSink`: stores the first accepted element, sets `_cancelled`, overrides `cancellation_requested()`; `_finish` returns the stored element or `None`.
- [x] 3.8 `_MatchSink(predicate, short_circuit_on, default)`: evaluates the predicate with the standard dispatch shape, sets `_cancelled` when `bool(r) is short_circuit_on`, overrides `cancellation_requested()`; `_finish` returns `short_circuit_on` if it fired else `default`.

## 4. Rewire stream.py's terminals

- [x] 4.1 `count()` → `_drive_to(_CountSink())`.
- [x] 4.2 `for_each(consumer)` → `_drive_to(_ForEachSink(consumer))`; `for_each_ordered(consumer)` → `_drive_to_sequential(_ForEachSink(consumer))`. The two now differ only in the drive call.
- [x] 4.3 `reduce()` → keep the existing `_UNSET` overload dispatch, then `_drive_to(_ReduceSink(identity, accumulator))`.
- [x] 4.4 `_min_max(comparator, asc)` → `_drive_to(_MinMaxSink(comparator, asc))`; `max()`/`min()` unchanged.
- [x] 4.5 `_match(...)` → `_drive_to(_MatchSink(...))`; `all_match`/`any_match`/`none_match` unchanged, including `none_match`'s inversion.
- [x] 4.6 `find_first()`/`find_any()` → `_drive_to(_FindSink())`.
- [x] 4.7 `_collect_mutable(supplier, accumulator)` → await the supplier via `_maybe_await` (once per composition), then `_drive_to(_MutableReductionSink(container, accumulator))`.
- [x] 4.8 Leave `collect(collector)`, `to_array()`, `iterator()`, `_concat`, `sequential()`/`parallel()` on `_compose()`/`_drive()` — verify by reading that `GeneratorBridgeSink` still has exactly these callers and no terminal reaches it.
- [x] 4.9 Remove the now-dead `isawaitable`/`is_async_callable`/`check_comparator_result_type` imports from `stream.py` if nothing there still uses them; run `uv run ruff check .`.

## 5. ParallelStream

- [x] 5.1 Override `_drive_to(terminal)` in `ParallelStream`: `begin({})`, iterate `self._compose()` inside `_maybe_aclosing`, `accept` each element, break on `terminal.cancellation_requested()`, `end()`, return `result()`.
- [x] 5.2 Rewrite `ParallelStream.find_first()`: unordered → `find_any()` as today; ordered → `_drive_to_sequential(_FindSink())`.
- [x] 5.3 Verify the abandoned-race teardown: a short-circuiting terminal on a `ParallelStream` must leave no pending task uncancelled and no exception unretrieved (the existing `finally:` in `_parallel()` should cover it — confirm with a test, do not assume).

## 6. Specs and protocol docs

- [x] 6.1 Update `TerminalSink`'s docstring in `sink.py` to state that a terminal may report `cancellation_requested()` and still receives `end()`. No behavior change to `sink.py`.
- [x] 6.3 **Added during implementation, beyond the planned scope:** `_SortedSink.end()` (`ops.py`) flushes its whole buffer downstream in one go with no driving loop in between, so it pushed past a terminal that had already cancelled — `peek()` still fired for every element after a `find_first()` was settled. Added a `cancellation_requested()` check between pushes, mirroring `_FlatMapSink`'s existing inner-loop check. Without it the change's headline benefit has a hole for any chain containing `sorted()`.
- [x] 6.2 Check whether `TerminalSink._finish`'s default body is still reached by any subclass; if every subclass overrides it, decide between deleting it and keeping it with a test rather than adding a coverage pragma.

## 7. Tests

- [x] 7.1 Run the existing suite unmodified first — every terminal-op test file passing without edits is the primary regression signal. Investigate any edit that seems necessary before making it.
- [x] 7.2 `reduce()` edge cases the rewrite could silently change: empty source with no identity (`None`), single element with no identity (returned without calling the accumulator), empty source with an identity (the identity), async accumulator.
- [x] 7.3 Cancellation from a terminal: `.peek(fn).any_match(p)` calls `fn` exactly once when the first element matches; `.peek(fn).find_first()` likewise; `count()`/`for_each()` still pull every element.
- [x] 7.4 `.flat_map(mapper).any_match(p)` stops mid-inner-expansion and closes the inner generator (mirror `tests/test_flat_map.py`'s existing tracked-generator pattern); `.flat_map(mapper).find_first()` takes exactly one inner element.
- [x] 7.5 Ordered drive: `for_each_ordered()` on a `ParallelStream` with the jumbled-source-plus-positional-delay pattern from `tests/test_for_each_ordered.py`; ordered and unordered `ParallelStream.find_first()` per `tests/test_find_first.py`.
- [x] 7.6 Parallel terminals: `count()`/`reduce()` on a `ParallelStream` match the sequential result; `any_match()` short-circuits and tears the race down with no unhandled exception or warning.
- [x] 7.7 Protocol-level coverage in `tests/test_sink.py` for the new `sink-protocol` scenarios: a terminal sink's cancellation visible at the head of a chain, and `end()`/`result()` after a terminal-initiated stop.

## 8. Verify

- [x] 8.1 `uv run pytest` — test count at or above baseline, coverage at or above baseline and above the 98% gate. `uv run pytest --cov-fail-under=98`.
- [x] 8.2 `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src`.
- [x] 8.3 Re-run both benchmark scenarios with interleaved before/after rounds. Record the numbers in the roadmap's Done entry whatever they show. A measured regression on the sequential path is a stop-and-reassess, not something to write up as a win.
- [x] 8.4 Confirm no public API change: no README parity-table or migration-log edit is needed, and every name added is private and unexported.
- [x] 8.5 Move the roadmap's **Now** terminal-sink item to **Done** with the behavior note from design Decision 4 (side-effecting callables no longer fire past a short-circuit) and the parallel-path limitation from Decision 3. Note that the **Next**-bucket `Collector` redesign is now unblocked, and that the small-cleanups item's `for_each_ordered`/`find_first` duplication entries are dissolved.
