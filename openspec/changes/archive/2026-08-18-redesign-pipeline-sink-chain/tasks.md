## 1. Baseline

- [x] 1.1 Record a pre-change benchmark: 20,000 elements through a chain of 8 `.map()` ops, best of 5, ns/element, on the dev interpreter — the number the post-change figure is compared against.
- [x] 1.2 Confirm the full suite is green before touching anything (`uv run pytest`), and note the current coverage percentage.

## 2. Sink protocol

- [x] 2.1 Create `src/snakestream/sink.py` with the `Sink` protocol: `async begin(state_map)`, `async accept(element)`, `async end()`, sync `cancellation_requested()`.
- [x] 2.2 Add a base for intermediate sinks that holds a `downstream`, propagates `begin()`/`end()` down the chain, and forwards `cancellation_requested()` to `downstream`.
- [x] 2.3 Add the terminal-sink shape: no `downstream`, container created in `begin()`, accumulation in `accept()`, finish in `end()`, value exposed via `result()`.
- [x] 2.4 Add the generator-bridge terminal sink: buffers pushed elements for the driving loop to drain and yield.
- [x] 2.5 Add any new composite/callable type aliases the protocol needs to `type.py` (not inline in `sink.py`).
- [x] 2.6 Add `tests/test_sink.py` covering the `sink-protocol` spec directly: lifecycle ordering (begin once, before all accepts; end once, after), begin/end on an empty source, zero/one/many pushes per accept, pushing from `end()`, state-map lookup and fresh-local-state fallback, two chains sharing one state map, cancellation propagation to the head, and terminal `result()` including the empty-source case.

## 3. Operation objects and sequential composition

- [x] 3.1 Introduce the operation-object shape in `stream.py`: `link(downstream) -> Sink` plus an optional shared-state factory, replacing the closure entries currently appended to `_chain`.
- [x] 3.2 Rewrite `BaseStream._sequential()` to link ops right-to-left onto a terminal sink instead of nesting generators, leaving `self._chain` unmutated.
- [x] 3.3 Rewrite `BaseStream._compose()` to build a fresh state map, link the chain onto the bridge sink, and drive it: `aclosing(source)`, `begin()`, per-element `accept()` + buffer drain + `cancellation_requested()` check, then `end()` + final drain.
- [x] 3.4 Verify `iterator()`, `_concat`, `sequential()`, `parallel()` and all 11 terminal ops still work unchanged against the new `_compose()` — no edits expected in `collector.py`.

## 4. Stateless intermediate ops as sinks

- [x] 4.1 Port `map()` to a sink, preserving the hoisted `is_async_callable` + first-invocation `isawaitable` safety-net dispatch.
- [x] 4.2 Port `filter()` to a sink with the same dispatch pattern; pushing nothing for a rejected element.
- [x] 4.3 Port `peek()` to a sink with the same dispatch pattern; always pushes the element through unchanged.
- [x] 4.4 Port `sorted()` to a sink: buffer in `accept()`, sort in `end()` (still routing through `merge_sort` when a comparator is given), push all elements downstream before awaiting `downstream.end()`.
- [x] 4.5 Port `flat_map()` to a sink: keep the up-front `iscoroutinefunction` rejection, iterate the inner stream's own composition directly (dropping the `collect(to_generator)` layer), and keep `aclosing()` on that composition per the `flat_map` cleanup requirement.
- [x] 4.6 Run the per-op suites (`test_map.py`, `test_filter.py`, `test_peek.py`, `test_sorted.py`, `test_flat_map.py`) plus the hypothesis property tests unmodified.

## 5. Stateful intermediate ops as sinks

- [x] 5.1 Port `distinct()` (`_DistinctOp`) to a sink taking its seen-set from the state map via `begin()`, with fresh-local fallback.
- [x] 5.2 Port `limit()` (`_LimitOp`) to a sink: check-and-reserve against the shared count with no suspension point between them, and report `cancellation_requested()` once `max_size` is reached. Remove the `await iterable.aclose()` reach-up; closing is now the driving loop's job.
- [x] 5.3 Port `skip()` (`_SkipOp`) to a sink taking its drop-count from the state map via `begin()`, with fresh-local fallback.
- [x] 5.4 Run `test_distinct.py`, `test_limit.py`, `test_skip.py` and the per-composition state-reset cases in `test_sequential.py` unmodified.

## 6. Parallel composition

- [x] 6.1 Rewrite `ParallelStream._parallel()` to build one shared state map per composition from the ops' state factories, replacing the `getattr(fn, "make_state", None)` introspection.
- [x] 6.2 Pass that same state map into every racing branch's `begin()`, so each branch's sinks for a given op share one state instance.
- [x] 6.3 Keep `_guarded()`'s shared-lock serialization of pulls and its close-under-lock behavior; confirm a branch pulling from an already-closed shared source still ends cleanly.
- [x] 6.4 Confirm `ParallelStream.find_first()`'s ordered path (`self._sequential(self._chain[:], self._stream)`) still works against the new `_sequential()` signature, adjusting the call rather than the behavior.
- [x] 6.5 Run `test_parallel.py`, `test_for_each_ordered.py`, `test_find_first.py`, `test_unordered.py` unmodified.

## 7. Verification

- [x] 7.1 Run the full suite unmodified (`uv run pytest`). Any test needing an edit to pass is evidence of a behavior change — justify it explicitly or fix the implementation, do not accommodate it.
- [x] 7.2 Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src`.
- [x] 7.3 Run `uv run pytest --cov-fail-under=98` and close any coverage gaps in the new `sink.py`.
- [x] 7.4 Re-run the 1.1 benchmark and record the actual before/after ns/element. If the gain is at or below parity, drop the performance claim from the change's write-up and state the architectural justification as the sole one.
- [x] 7.5 Verify no public API surface changed (no README parity-table or migration-log edit should be needed); confirm nothing in `collector.py` was touched.

## 8. Wrap-up

- [x] 8.1 Move the Sink-chain item from **Next** to **Done** in `roadmap.md`, recording the measured benchmark result and the two scoping decisions taken (push internally only; terminal seat defined now).
- [x] 8.2 Note in the roadmap's Collector-redesign entry that the terminal seat now exists, so that item is a plug-in rather than a protocol change.
