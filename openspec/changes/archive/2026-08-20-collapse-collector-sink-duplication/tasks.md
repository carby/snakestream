## 1. Baseline

- [x] 1.1 Run `uv run pytest` and record the passing count and coverage percentage — this is the number every part below must still produce.
- [x] 1.2 Confirm the duplication claims still hold before editing: `summing_int`/`summing_long` byte-identical bodies, the three `averaging_*` byte-identical, `summing_double` differing only by the `0.0` seed and `float()` cast. If any has drifted since 2026-08-19, report it and adjust the part rather than forcing the collapse.

## 2. Part (a) — collapse the summing/averaging bodies

- [x] 2.1 Add private `_summing(seed, coerce)` in `collector.py`. (Shipped with the test *inside* the loop, not hoisted — hoisting duplicates the loop and trips the project's C901 gate. See design.md decision 1, reversed with the user.)
- [x] 2.2 Add private `_averaging()` in `collector.py` — no parameters; the three public averaging bodies are identical.
- [x] 2.3 Rewrite `summing_int` and `summing_long` as wrappers over `_summing(0, None)`, and `summing_double` over `_summing(0.0, float)`, each keeping its own return annotation (`int`, `int`, `float`).
- [x] 2.4 Rewrite `averaging_int`, `averaging_long` and `averaging_double` as wrappers over `_averaging()`, each keeping its `float` return annotation.
- [x] 2.5 Reword the `collector.py:65-69` comment so it defends the six *names* (Java distinguishes by primitive; Python's numeric tower does not) and no longer reads as defending six bodies.
- [x] 2.6 Run `uv run pytest` — all tests pass unmodified, no test edits in this part.

## 3. Part (b) — hoist the sink dispatch triple

- [x] 3.1 Grep `src/` and `tests/` for `_predicate`, `_mapper`, `_consumer`, `_accumulator` and `_comparator` as *attribute* accesses on the eight affected sinks; list every hit that will need the rename, including test doubles and assertions.
- [x] 3.2 Add the dispatch mixin to `callable_dispatch.py` with a single `_init_dispatch(fn)` method setting `self._fn`, `self._is_async` and `self._checked`. Plain method, no `__init__`, so it stays out of the MRO. Point the existing canonical-shape comment at it.
- [x] 3.3 Convert `_FilterSink`, `_MapSink` and `_PeekSink` in `ops.py`: mix in, call `_init_dispatch(...)` from `__init__`, rename the attribute inside `accept()`. Constructor parameter names and `Predicate`/`Mapper`/`Consumer` annotations are unchanged.
- [x] 3.4 Convert `_ForEachSink`, `_ReduceSink`, `_MinMaxSink`, `_MutableReductionSink` and `_MatchSink` in `terminals.py` the same way. `_MatchSink` keeps its own `self._cancelled = False` — that is short-circuit state, not dispatch state.
- [x] 3.5 Verify each of the eight `accept()` bodies differs from its pre-change form **only** by the attribute rename: same branch structure, same inlined dispatch, no call added to the per-element path. Any per-element restructuring noticed here gets reported, not applied.
- [x] 3.6 Apply the mechanical attribute renames in the tests found at 3.1 — attribute names only, never assertion semantics. (None needed: 3.1 found no test reaching for these as sink attributes, so `tests/` is untouched by this part.)
- [x] 3.7 Run `uv run pytest`.

## 4. Part (c) — one grouping helper

- [x] 4.1 Add private `_group_into(composition, key_fn, initial)` in `collector.py`, running the five-branch dispatch once and returning the populated `dict[Any, list]`.
- [x] 4.2 Rewrite `grouping_by` to call it with its classifier unwrapped and an empty `dict`, keeping the `downstream`-mapping comprehension at the call site (item 2 rewrites that line).
- [x] 4.3 Rewrite `partitioning_by` to call it with a `key_fn` applying `bool(...)` to the predicate result and an initial `{True: [], False: []}`, keeping its own `downstream`-mapping comprehension.
- [x] 4.4 Confirm the preserved edge behaviors still hold in the suite: truthy non-`bool` predicate results land in the `True` bucket; both partitions appear for an empty source; `grouping_by` still accepts arbitrary classifier keys.
- [x] 4.5 Run `uv run pytest`.

## 5. Part (d) — `StatefulOp` subclasses `StatelessOp`

- [x] 5.1 Grep `src/` and `tests/` for `isinstance(..., StatelessOp)` and `isinstance(..., StatefulOp)` (and any `type(...) is` equivalent). If anything distinguishes the two by type, **drop this part** and say so — do not work around it.
- [x] 5.2 Make `StatefulOp` subclass `StatelessOp` in `sink.py`, deleting its duplicated `__init__` and `_sink_cls` declaration and keeping only the `link()` override that inserts `self` before the stored args.
- [x] 5.3 Keep both docstrings, since the shared-state distinction they draw is no longer expressed by the class hierarchy.
- [x] 5.4 Run `uv run pytest`.

## 6. Verification

- [x] 6.1 `uv run pytest --cov-fail-under=98` — the coverage gate, including `_summing`'s new `coerce is None` branch.
- [x] 6.2 `uv run ruff check .` and `uv run ruff format --check .`.
- [x] 6.3 `uv run ty check src`.
- [x] 6.4 Confirm the test count matches the 1.1 baseline and that no test was changed except the mechanical attribute renames from 3.6.
- [x] 6.5 Confirm no public API changed: the six summing/averaging names, `grouping_by` and `partitioning_by` keep their signatures and return types, and every other name touched is private. No README edit.
- [x] 6.6 Record the net line count removed against the design's ~150-line estimate. **Came in materially under: -69 code lines** (comments/docstrings excluded), or -79 coverage-measured statements, against ~150 estimated. Part (a) delivered -58 of it; (b) -6 in `ops.py` and -10 in `terminals.py` against +8 for the mixin; (d) -3. The estimate counted the raw span of the six deleted bodies including their blank and comment lines, and this change also adds explanatory comments the old copies did not carry.

## 7. Roadmap

- [x] 7.1 Move item 1 from **Now** to **Done** in `roadmap.md`, writing up what actually landed — including any part dropped at 5.1 or adjusted at 1.2 — and renumber the remaining Now items.
