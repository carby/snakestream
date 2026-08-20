## 1. Foundations in `sink.py` and `type.py`

- [x] 1.1 Add `Box` to `sink.py` (`__slots__ = ("value",)`, any initial value) and make `Counter` subclass it with an `int` default of `0`, keeping `Counter`'s name and docstring; verify no importer of `Counter` changes (design Decision 3).
- [x] 1.2 Move `_UNSET` from `terminals.py` to `sink.py`, delete `collector.py`'s duplicate sentinel, and update `stream.py`'s `from snakestream.terminals import _UNSET` to import from `sink.py`. Leave no re-export behind (design Decision 4).
- [x] 1.3 Make `TerminalSink.begin()` and `end()` await what `_create_container()` / `_finish()` return, via the existing `_maybe_await`. Confirm every existing sink still passes its plain value straight through (design Decision 6).
- [x] 1.4 Add `A` (accumulation-type `TypeVar`), `Finisher` and `Combiner` to `type.py`; reuse the existing `Supplier` and `BiConsumer` for the other two `Collector` parts (design Decision 11).
- [x] 1.5 Run the full suite — everything above is behaviour-neutral and must stay green before any collector is touched.

## 2. The `Collector` shape and its adapter

- [x] 2.1 Add the public `Collector(supplier, accumulator, combiner=None, finisher=None)` class to `collector.py`: `__slots__`, generic in `[T, A, R]`, identity equality, docstring stating that the accumulator mutates and its return value is ignored, and that `combiner` is retained but never invoked (spec `collector-protocol`, design Decisions 1–2).
- [x] 2.2 Add `_CollectorSink(AsyncDispatch, TerminalSink)` to `collector.py`: `_create_container()` returns `supplier()`, `accept()` runs the accumulator through the canonical inlined dispatch shape, `_finish()` returns `finisher(container)` or the container when there is no finisher. Exactly one `AsyncDispatch` triple, for the accumulator (design Decision 5).
- [x] 2.3 Add `StreamingCollector` wrapping a `(composition) -> AsyncGenerator` callable, and make `to_generator` an instance of it, keeping `to_generator(gen)` directly callable (design Decision 7).
- [x] 2.4 Rewrite `Stream.collect()`'s single-argument branch: a `Collector` drives `_CollectorSink` via `_drive_to`; a `StreamingCollector` composes through the bridge and returns the generator un-awaited; anything else raises `StreamBuildException` naming `Collector` and pointing at `to_generator`. The 3-arg branch is untouched (design Decision 10).
- [x] 2.5 Update `collect()`'s overloads and `to_array()`'s annotation for the new argument type; keep `to_array()`'s body as `collect(to_list)`.

## 3. Rewrite the stateless collectors

- [x] 3.1 `to_list` — a module-level `Collector` instance over `list`/`list.append`, so `collect(to_list)` keeps working uncalled (design Decision 8). Delete the old `async def to_list`.
- [x] 3.2 `to_set()` — `Collector(set, set.add)`, keeping its parentheses.
- [x] 3.3 `joining(delimiter, prefix, suffix)` — list container, finisher applying prefix/delimiter/suffix (spec `collector-joining`).
- [x] 3.4 `counting()` — `Counter` container, `_CountSink`-free, finisher returning `.value` (spec `collector-counting-summing-averaging`).
- [x] 3.5 Run the suite; `test_to_array.py`, `test_joining.py`, `test_counting.py`, `test_to_set.py` and every test using `collect(to_list)` must pass unchanged.

## 4. Rewrite the collectors that dispatch a user callable per element

Each of these needs its classification state on the supplier-made container, never in the factory closure (design Decision 5).

- [x] 4.1 `_summing(mapper, seed, coerce)` and `_averaging(mapper)` return `Collector`s over a private container holding the running total (and count) plus the mapper's `is_async`/`checked` flags; the six public wrappers keep their names, signatures and distinct return annotations, and the comment defending six *names* stays.
- [x] 4.2 `min_by`/`max_by` — container holds the running extremum (seeded `_UNSET`) plus the comparator's dispatch flags; keep `check_comparator_result_type` and the first-of-tied-elements tie-break, and delete `_extremum` (spec `collector-min-max`).
- [x] 4.3 `reducing` — all three overloads onto one `Collector`; container holds the accumulator (seeded `identity` or `_UNSET`) plus the mapper's and binary operator's dispatch flags, using `_classify_step`. Overload resolution stays in the factory, where it runs once.
- [x] 4.4 `to_map` — container holds the `dict` plus three dispatch triples (key, value, merge); duplicate-key `ValueError` and the `merge_function` path unchanged.
- [x] 4.5 Run the suite; `test_summing.py`, `test_averaging.py`, `test_min_by.py`, `test_max_by.py`, `test_reducing.py`, `test_to_map.py` must pass unchanged.

## 5. `grouping_by` / `partitioning_by`

- [x] 5.1 Rewrite `_group_into` as the shared accumulator step: classify the key, `setdefault` that key's container from `downstream.supplier()`, run `downstream.accumulator`. Keep `partitioning_by`'s separate `coerce_key` and the comment explaining why a `bool()` wrapper round the predicate is unimplementable (design Decision 9).
- [x] 5.2 `grouping_by(classifier, downstream=to_list)` — `Collector` whose finisher awaits `downstream.finisher` per key; delete `_generator_of` and the buffer-then-replay comprehension (spec `collector-grouping-by`).
- [x] 5.3 `partitioning_by(predicate, downstream=to_list)` — same, with both `True`/`False` containers created up front so an empty partition still finishes to the downstream's empty-input result (spec `collector-partitioning-by`).
- [x] 5.4 Reject a non-`Collector` `downstream` in both factories with `StreamBuildException`, at factory-call time rather than per element.
- [x] 5.5 Run the suite; `test_grouping_by.py` and `test_partitioning_by.py` must pass unchanged, including the async-predicate case at `tests/test_partitioning_by.py:37`.

## 6. New tests

- [x] 6.1 `tests/test_collector.py` — a user-defined `Collector`: all-sync parts, all-async parts, no finisher (container is the result), a finisher that changes the result type, and an accumulator whose return value must be ignored.
- [x] 6.2 The reuse contract: the same `Collector` instance collecting two streams in sequence and two concurrently, asserting no container and no classification state is shared — the leak Decision 5 exists to prevent. Include one `.parallel()` case.
- [x] 6.3 `combiner` is never invoked: a `Collector` whose combiner raises, collected on both a sequential and a `.parallel()` stream.
- [x] 6.4 Rejection paths: a plain `async def` collector passed to `collect()`, and a plain callable passed as `downstream` to both `grouping_by` and `partitioning_by`, each raising `StreamBuildException` without consuming the stream.
- [x] 6.5 `collect(to_generator)` still returns a lazily-iterable `AsyncGenerator` without being awaited, and `to_generator(composition)` is still directly callable.
- [x] 6.6 Per-key/per-partition container isolation for a mutable downstream container (spec scenarios in `collector-grouping-by` / `collector-partitioning-by`).

## 7. Measure, verify, document

- [x] 7.1 Benchmark `collect(to_list)`, `collect(counting())` and `collect(summing_int(len))` before vs. after — interleaved reps in one process over ~200k elements, as `collapse-collector-sink-duplication` did. A regression on the scale that sank `add-callsite-dispatch` is the stop condition; record the numbers in the change for the archive note.
- [x] 7.2 Confirm no `is_async`/`checked` state is stored on any `Collector` or in any factory closure — grep `collector.py` for assignments to those names outside a supplier-made container.
- [x] 7.3 Full CI parity locally: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`, `uv run ty check src`, `uv run pytest --cov-fail-under=98`.
- [x] 7.4 README: rewrite the `collect(collector: Callable)` row for the `Collector` type, document the `Collector` class and `StreamingCollector` above the Collectors table, and update the `grouping_by`/`partitioning_by` rows' `downstream` description.
- [x] 7.5 README migration log: add the two `0.3.5 -> next` entries (callable collectors, callable `downstream`), each naming the replacement and mentioning `grouping_by`'s now-interleaved downstream accumulation.
- [x] 7.6 `roadmap.md`: move item 1 from **Now** to **Done** with the outcome, and renumber item 2 (the four remaining Java 8 `Collectors`), noting it is now unblocked.
