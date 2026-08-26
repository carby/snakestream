## 1. Baseline

- [x] 1.1 Record the pre-change gate output to compare against: `uv run pytest` (note the coverage line, and missed statements/branches/partial-branches, not just the percentage), `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check src` (save the full output, not just the exit code).
- [x] 1.2 Confirm the tripwire's starting point: `git grep -l "snakestream.collector" -- tests/ | wc -l` is 46, and `grep -rn "snakestream.collector" README.md CLAUDE.md` names the sites the docs step will fix.

## 2. `StreamException`

- [x] 2.1 Add `class StreamException(Exception)` to `src/snakestream/exception.py` with a docstring stating it is a base to catch, never raised directly, and reparent `StreamBuildException` and `IllegalStateException` onto it.
- [x] 2.2 Add tests covering the `exception-hierarchy` spec's scenarios: a `StreamBuildException` and an `IllegalStateException` each caught by `except StreamException`; a `StreamException` propagating uncaught through `except ValueError`; `issubclass` checks for both leaves and for `StreamException` deriving from `Exception`.
- [x] 2.3 Run the suite; confirm the existing `except StreamBuildException` / `except IllegalStateException` tests still pass untouched.

## 3. Split `collector.py`

- [x] 3.1 Create `src/snakestream/collectors.py` with a module docstring naming it the factory holder (Java's `Collectors`) and stating the one-way import edge to `collector.py`.
- [x] 3.2 Move the factory half verbatim — `to_list` (line ~125) through `to_collection` (end of file) — preserving current order, with no renaming, reordering or reformatting. This carries `SummaryStatistics`, the nine `_*Box` dataclasses, and `_summing`, `_averaging`, `_summarizing`, `_extremum`, `_group_into`, `_finish_groups`, `_check_downstream`, `_finish_collecting_and_then`.
- [x] 3.3 Split the import block: `collector.py` keeps what the protocol half uses (`_maybe_aclosing`, `AsyncDispatch`, `_maybe_await`, `TerminalSink`, and the `Supplier`/`BiConsumer`/`Combiner`/`Finisher` aliases); `collectors.py` takes the rest (`is_new_extremum`, `Box`, `_UNSET`, `IllegalStateException`, `StreamBuildException`, `is_async_callable`, `_classify_step`, the remaining `type.py` aliases) plus `from snakestream.collector import Collector`.
- [x] 3.4 Update `collector.py`'s module-level comment above `to_list` — the "A factory, like every other collector here" note belongs with the factories now, reworded for its new module.
- [x] 3.5 Remove any import left unused on either side; confirm `ruff check` reports no `F401` in either module.
- [x] 3.6 Update `src/snakestream/stream.py:9` to import `Collector`, `StreamingCollector` and `_CollectorSink` from `snakestream.collector` and `to_list` from `snakestream.collectors`.
- [x] 3.7 Update `stream.py`'s `collect()` error message (`:297`) — it names `snakestream.collector.Collector`, which is still correct, so verify rather than assume.
- [x] 3.8 Verify the import edge is one-way: `grep -n "collectors" src/snakestream/collector.py` returns nothing, and a clean-interpreter `uv run python -c "import snakestream"` succeeds.

## 4. Update the test imports

- [x] 4.1 Rewrite factory imports across `tests/` from `snakestream.collector` to `snakestream.collectors`, leaving `to_generator` on `snakestream.collector`. `tests/test_collector.py` legitimately imports from both afterwards.
- [x] 4.2 Run `git diff -U0 -- tests/` and confirm every changed line is an import line. Any other edit means the change went wider than the split — stop and investigate rather than absorbing it.
- [x] 4.3 Run the full suite; all tests pass with assertions unchanged.
- [x] 4.4 Compare coverage to task 1.1: check missed statements, branches and partial branches are identical. A moved-statement change should not uncover anything; treat only a change in those counts as a lost test, not a change in the percentage.

## 5. `_derive_executor()`

- [x] 5.1 Add `Stream._derive_executor(executor)` to `src/snakestream/stream.py`, carrying the twelve-line mode-switch docstring currently duplicated across `sequential()` and `parallel()`, and calling `self._derive(self._chain, executor)`.
- [x] 5.2 Reduce `sequential()` and `parallel()` to one-line docstrings naming their mode and delegating to `_derive_executor(SEQUENTIAL)` / `_derive_executor(RACING)`.
- [x] 5.3 Run the suite — `pipeline-immutability` and the mode-switch tests are the ones that would catch a mistake here, since the receiver must still be consumed.

## 6. `TerminalSink`'s awaitable contract

- [x] 6.1 Add a paragraph to `TerminalSink`'s docstring in `src/snakestream/sink.py` stating that `_create_container()` and `_finish()` may return awaitables, since `begin()`/`end()` route both through `_maybe_await`, and naming the three dependents (`_CollectorSink._create_container`, and `grouping_by`'s and `partitioning_by`'s sync `_finish`, which return an un-awaited coroutine).
- [x] 6.2 Confirm no `await` was added at any of the three dependent sites — documenting the contract, not changing it, is the whole task.

## 7. `Box` as a dataclass

- [x] 7.1 Convert `Box` in `src/snakestream/sink.py` to `@dataclass(slots=True)` with `value: Any = None`, keeping its docstring.
- [x] 7.2 Verify the conversion is behaviour-identical: same slot names, no `__dict__`, and `Box()` / `Box(0)` construct as before — the same check story 6 of the previous batch ran over its nine containers.
- [x] 7.3 Run the suite; `counting()` and `ops.py`'s two `make_shared_state()` bodies are the call sites that exercise it.

## 8. Documentation

- [x] 8.1 Update README's collector table intro and any prose naming `collector.py` as the factories' home; leave the `to_generator` quickstart import at line 9 unchanged and confirm it still resolves.
- [x] 8.2 Add a README Migration entry for the import-path break: the full list of moved names, the `ImportError` failure mode, that `to_generator` and `Collector` did not move, and the reason (Java's `Collector`/`Collectors` pair). Reference `openspec/changes/split-collector-protocol-and-factories`.
- [x] 8.3 Add a README Migration entry, or a line in the same one, noting `StreamException` as an added non-breaking base.
- [x] 8.4 Update `CLAUDE.md`'s Collectors section to name `collectors.py` as the factory module and `collector.py` as the protocol, and confirm its existing `_derive_executor()` reference in "Sequential vs. parallel execution" is now accurate.
- [x] 8.5 Do not edit historical Migration entries that mention `collector.py` — the log is read chronologically and was true at its release, the same rule the previous batch applied to the `redesign-collector-shape` entry.

## 9. Gate

- [x] 9.1 `uv run pytest` — full suite green.
- [x] 9.2 `uv run ruff check .` and `uv run ruff format --check .` clean.
- [x] 9.3 `uv run ty check src` — diff the output against task 1.1's, not just the exit code.
- [x] 9.4 `uv run pytest --cov-fail-under=98` passes.
- [x] 9.5 `openspec validate split-collector-protocol-and-factories --strict` passes.
- [x] 9.6 Confirm the change touched no per-element path: review the diff for edits inside `accept()` bodies or accumulator inner functions. There should be none, which is why no benchmark run is needed.
