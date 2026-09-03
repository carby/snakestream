## 1. Baseline

- [x] 1.1 Record the green baseline so any later failure is attributable: `uv run pytest` passes; note the collected test count and the total coverage figure for comparison in task 8.
- [x] 1.2 Record the exact rename set from the import graph rather than from the proposal's table, so nothing is taken on trust. An AST pass over `src/snakestream/*.py` collecting every `ast.ImportFrom` whose module starts with `snakestream` must report exactly the 27 underscore-prefixed names in proposal.md — no more, no fewer. A discrepancy means the table is stale and must be reconciled before any edit.
- [x] 1.3 Record the story-2 set the same way: the bare module-level names in `execution.py` and `sort.py` that no other module in `src/snakestream` imports must be exactly `stream_through`, `group_through`, `race_through`, `feed_through`, `drain`, `Sequential`, `Racing`, `merge_sort`. Confirm `Executor`, `SEQUENTIAL` and `RACING` are *not* in that set — `stream.py` imports all three.
- [x] 1.4 Record the pre-sweep occurrence count of each of the 27 names across `src/`, `tests/`, `CLAUDE.md` and `README.md` (`grep -rc`), so task 8.2's "zero residue" check has a denominator. `_UNSET` (~30 in `src/`) and the nine `Op` subclasses are the ones with enough sites to hide a miss.

## 2. The enforcement check (written first, so it fails before the sweep)

- [x] 2.1 Create `tests/test_name_visibility.py` with the cross-module private-import check described in design decision 3: walk every `src/snakestream/*.py` with `ast.walk`, keep `ImportFrom` nodes whose `module` starts with `snakestream`, and collect every imported name beginning with `_`. Walk the whole tree, not just module-level statements, so `stream.py`'s function-local `StreamBuilder` import is covered.
- [x] 2.2 Verify the failure message names importing module, defining module and name, as the spec requires — assert on the message produced from a synthetic finding, not only on the pass path.
- [x] 2.3 Verify the check actually fails on a violation: feed it a synthetic module source containing `from snakestream.sink import _UNSET` and confirm it reports one finding. This is the scenario "A cross-module private import is introduced"; a check only ever exercised on clean input is not evidence.
- [x] 2.4 Verify the check inspects only `src/snakestream`: confirm it reports nothing for the existing `tests/` modules that import private names (`test_sequential.py`'s `_wrap_sink`, `test_find_first.py`'s `_in_flight`), covering the scenario "A test's private import does not fail the check".
- [x] 2.5 Run it against the package as it stands and confirm it reports exactly the 27 names from task 1.2. This is the red state the sweep turns green, and it double-checks 1.2 by a second route.

## 3. Story 1 — the renames, leaf modules first

Rename at the definition and at every use site. No signature, argument, branch or call-order change in any task in this section; each is verified by `git diff` showing only definition lines, import lines and use sites.

- [x] 3.1 `type.py`: `_Aiter` -> `Aiter`, `_C` -> `C`, `_M` -> `M` (design decision 4). Leave `_SupportsAdd` private — it is used only in `type.py`. Update the comment on `_M` that refers to `_C` by name. Verify `uv run ty check src` passes: these are TypeVars, so a missed site is a typing error rather than a runtime one.
- [x] 3.2 `callable_dispatch.py`: `_maybe_await` -> `maybe_await`, `_classify_step` -> `classify_step`; update `sink.py` and `collectors.py`.
- [x] 3.3 `sink.py`: `_UNSET` -> `UNSET`, `_unseeded` -> `unseeded`, `_UnseededSink` -> `UnseededSink`; update `collectors.py`, `stream.py`, `terminals.py`. Leave `_ArgsOp` private — nothing outside `sink.py` imports it. Verify `reducing()`'s signature now renders `identity=UNSET` (`uv run python -c "import inspect, snakestream.collectors as c; print(inspect.signature(c.reducing))"`).
- [x] 3.4 `ordering.py`: `_split_point` -> `split_point`; update `execution.py`. Verify the module now reads consistently — `is_ordered()` and `split_point()`, the two folds its docstring pairs, no longer differ in visibility marking. Update the module docstring and `OrderDemand`'s docstring where they name `_split_point()`.
- [x] 3.5 `execution.py`: `_maybe_aclosing` -> `maybe_aclosing`; update `collector.py`. Leave `_maybe_aclose`, `_racing_branches`, `_wrap_sink`, `_copy_into`, `_Window`, `_guarded`, `_in_flight`, `_IN_FLIGHT_PER_WORKER`, `_releasable`, `_release_in_order`, `_run_ordered_tail` private — verified module-local in task 1.2.
- [x] 3.6 `comparator.py`: `_ASYNC_COMPARATOR_MESSAGE` -> `ASYNC_COMPARATOR_MESSAGE`; update `sort.py`. Renamed, not moved (design decision 4). Leave `_reject_async_comparator` private — only `comparator.py` calls it; update its docstring's reference to the constant.
- [x] 3.7 `collector.py`: `_CollectorSink` -> `CollectorSink`; update `stream.py`. Leave `_NO_CHARACTERISTICS` and `_stream` private.
- [x] 3.8 `terminals.py`: `_CountSink` -> `CountSink`, `_ForEachSink` -> `ForEachSink`, `_ReduceSink` -> `ReduceSink`, `_MinMaxSink` -> `MinMaxSink`, `_FindSink` -> `FindSink`, `_MatchSink` -> `MatchSink`; update `stream.py`.
- [x] 3.9 `ops.py`: drop the underscore from all nine `Op` subclasses (`_FilterOp`, `_MapOp`, `_PeekOp`, `_SortedOp`, `_UnorderedOp`, `_FlatMapOp`, `_DistinctOp`, `_LimitOp`, `_SkipOp`); update `stream.py`. Leave the nine `*Sink` classes in `ops.py` private — each is referenced only by its own op's `_sink_cls`, confirmed in task 1.2.
- [x] 3.10 `sink.py`: delete `removeprefix("_")` from `Op.__repr__` and update its docstring example from `_FlatMapOp` to `FlatMapOp` (design decision 5). Add the sentence the decision calls for: an underscored `Op` subclass would now render with the underscore, which is the correct failure because such a class would be violating the rule. Verify `repr()` of a built pipeline is byte-identical to the baseline — `uv run pytest -k repr` passes unchanged.
- [x] 3.11 Run the task 2.1 check: it must now report zero findings. Run `uv run pytest`; the count from task 1.1 must be unchanged except for the new `test_name_visibility.py` tests.

## 4. Story 2 — the reverse pass

- [x] 4.1 `execution.py`: `stream_through` -> `_stream_through`, `group_through` -> `_group_through`, `race_through` -> `_race_through`, `feed_through` -> `_feed_through`, `drain` -> `_drain`, `Sequential` -> `_Sequential`, `Racing` -> `_Racing`. `Executor`, `SEQUENTIAL` and `RACING` are unchanged. Verify by `git diff` that `SEQUENTIAL = _Sequential()` and `RACING = _Racing(PROCESSES)` are the only construction sites and that `stream.py` is untouched by this task.
- [x] 4.2 `execution.py`: update the module docstring and every docstring naming a renamed verb — `Executor.value()`'s generic-default docstring names `drain`, `Sequential.value()`'s override docstring carries the +125% measurement, and `_race_through`'s describes the second gear. The figures and the reasoning do not change; only the names do.
- [x] 4.3 `sort.py`: `merge_sort` -> `_merge_sort`. Update the five docstring and comment references to it in `sort.py`, plus the one inside `ASYNC_COMPARATOR_MESSAGE` in `comparator.py` — that string is user-facing, so verify the exception message a caller sees still reads correctly with the new name (`uv run pytest -k comparator` passes; check the assertion text in `tests/test_comparator*.py` for a literal match on the old name).
- [x] 4.4 Confirm story 2 introduced no new violation of story 1's rule: re-run the task 2.1 check, still zero findings, and re-run task 1.3's scan — the story-2 set must now be empty.

## 5. Story 3 — `PROCESSES` leaves the export surface

- [x] 5.1 Remove `from snakestream.execution import PROCESSES as PROCESSES` from `src/snakestream/__init__.py`. Verify `uv run python -c "from snakestream import PROCESSES"` raises `ImportError` and `uv run python -c "import snakestream; snakestream.Stream"` still works.
- [x] 5.2 Remove `PROCESSES` from `stream.py`'s `from snakestream.execution import PROCESSES as PROCESSES, RACING, SEQUENTIAL, Executor`, keeping the other three. Verify `uv run python -c "from snakestream.stream import PROCESSES"` raises `ImportError` and that `grep -n "PROCESSES" src/snakestream/stream.py` returns nothing.
- [x] 5.3 Verify the definition is untouched: `snakestream.execution.PROCESSES` still imports and equals its baseline value, and `RACING` is still built from it at import.
- [x] 5.4 Update `tests/test_package_exports.py`: `test_processes_exported_from_top_level_package` inverts into an assertion that neither `snakestream` nor `snakestream.stream` exposes the name, and the `_IN_FLIGHT_PER_WORKER` test's closing comment — "PROCESSES is unaffected — it names a concept with a Java counterpart" — is replaced with the argument that now holds for both constants. Verify the module still passes and no longer asserts `"PROCESSES" in exported`.

## 6. Docs

- [x] 6.1 `CLAUDE.md`: update the "Sequential vs. parallel execution" code block and prose for story 2's seven renames, and the "The ordering barrier" section for `split_point`. Verify by `grep -n "stream_through\|group_through\|race_through\|feed_through\|drain\|_split_point" CLAUDE.md` that every hit reads with the new name.
- [x] 6.2 `CLAUDE.md`: update the "Collectors" section (`_CollectorSink` twice) and the "Python's data model" section (`_FlatMapOp -> flat_map`).
- [x] 6.3 `CLAUDE.md`: record the rule itself — a short paragraph stating that a leading underscore on a module-level name means module-local use, that `tests/` may import anything, that class members are unaffected, and that `tests/test_name_visibility.py` enforces the first half. Place it where a contributor meets it before reading the architecture sections.
- [x] 6.4 `README.md`: add the Migration-log entry for `PROCESSES` per design's Migration Plan — both dropped import paths, the constant keeping its name in `snakestream.execution`, and the fact that assigning to it never changed the worker count because `RACING` binds it at import. Verify no parity-table row changes: no Java-counterpart method was added, renamed or removed.
- [x] 6.5 Confirm no other doc claims a name this change moved: `grep -rn` each of the 35 old names across `README.md` and `CLAUDE.md`; expected residue is zero apart from the new Migration entry, which names `PROCESSES` deliberately.

## 7. Roadmap

- [x] 7.1 Add the **Done** entry: the rule as adopted, the 27 + 8 + 1 shape, decision 1's rejection of `__init__.py`-as-boundary and decision 3's rejection of `PLC2701`-for-now with the preview-flag and annotation-only reasons, so neither is re-proposed from scratch. Note that the `PROCESSES` removal supersedes the 2026-08-26 entry that added the export.
- [x] 7.2 Check the roadmap's **Done** section for entries whose text this change makes stale — in particular the 2026-08-26 `PROCESSES` export entry and any entry naming a renamed symbol — and correct the sentence rather than the line number, per the house rule on citing the origin.

## 8. Gates

- [x] 8.1 `uv run pytest` passes with the baseline count plus the new `test_name_visibility.py` tests, and total coverage is unchanged from task 1.1 — a rename that changed behaviour would move it.
- [x] 8.2 Zero residue: `grep -rn` each old name from tasks 1.2 and 1.3 across `src/`, `tests/`, `CLAUDE.md` and `README.md` returns nothing, except `PROCESSES` in `execution.py`, in README's naming-rationale paragraph and in the new Migration entry.
- [x] 8.3 `uv run ruff check .`, `uv run ruff format --check .` (including this change's markdown files — the house has tripped on markdown fences before), and `uv run ty check src` all pass.
- [x] 8.4 `uv run pytest --cov-fail-under=98` passes, matching the CI coverage gate.
- [x] 8.5 `openspec validate name-by-visibility-not-underscore --strict` passes, and the change is ready to archive.
