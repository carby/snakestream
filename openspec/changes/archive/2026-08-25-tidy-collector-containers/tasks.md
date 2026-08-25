## 1. Collector containers to `@dataclass(slots=True)`

- [x] 1.1 Add `from dataclasses import dataclass, field` to `collector.py`'s imports.
- [x] 1.2 Convert `_SumBox` — `total: int | float` required first, `is_async: bool = False`, `checked: bool = False`. Verify `_summing`'s `_SumBox(seed)` call is unchanged.
- [x] 1.3 Convert `_AvgBox` — `total: float = 0.0`, `count: int = 0`, `is_async: bool = False`, `checked: bool = False`. Zero-arg construction preserved.
- [x] 1.4 Convert `_SummaryBox` — `total: int | float` required first (it takes `seed`), then `count: int = 0`, `least: int | float | None = None`, `greatest: int | float | None = None`, `is_async: bool = False`, `checked: bool = False`. Field *order* changes because a required field cannot follow a defaulted one; the only construction site is positional-with-one-arg (`_SummaryBox(seed)`), so it still binds `total`. Confirm no other site constructs it.
- [x] 1.5 Convert `_ExtremumBox` — `found: Any = _UNSET`, `is_async: bool = False`, `checked: bool = False`. `_UNSET` is a plain `object()` and is accepted as a default without a factory; confirm the shared-sentinel `is` comparison in `_extremum` still holds.
- [x] 1.6 Convert `_ReduceBox` — `acc: Any` required first, then the four `False` flags.
- [x] 1.7 Convert `_ToMapBox` — `result: dict[Any, Any] = field(default_factory=dict)` plus the six `False` flags.
- [x] 1.8 Convert `_GroupBox` — `groups: dict[Any, Any]` required first (both suppliers pass it), then the four `False` flags. No `default_factory`: the dict is supplied, not defaulted.
- [x] 1.9 Convert `_MappingBox` — `container: Any` required first, then the four `False` flags.
- [x] 1.10 Convert `_CollectAndThenBox` — `container: Any` required first, then `acc_is_async: bool = False`, `acc_checked: bool = False`.
- [x] 1.11 Read the nine converted classes back against the originals: every field name, type and default identical, no field dropped, no `__dict__` introduced (each carries `slots=True`).

## 2. Delete `Counter`

- [x] 2.1 Remove the `Counter` class from `sink.py`. Leave `Box` and its docstring untouched.
- [x] 2.2 `ops.py`: drop `Counter` from the `snakestream.sink` import, add `Box`; change `_LimitOp.make_shared_state()` and `_SkipOp.make_shared_state()` to `-> Box` returning `Box(0)`.
- [x] 2.3 `collector.py`: drop `Counter` from the `snakestream.sink` import, add `Box`; in `counting()` change `Collector(Counter, ...)` to `Collector(lambda: Box(0), ...)` and retype `_accumulate`/`_finish`'s `container` parameter to `Box`.
- [x] 2.4 `terminals.py`: update `_CountSink`'s docstring — both mentions of `Counter` become `Box`. The reasoning it gives is unchanged.
- [x] 2.5 `grep -rn "Counter" src/` returns nothing.

## 3. `to_map` raises `IllegalStateException`

- [x] 3.1 `collector.py`: import `IllegalStateException` alongside `StreamBuildException` from `snakestream.exception`; change `to_map`'s duplicate-key `raise ValueError(f"Duplicate key: {key!r}")` to `raise IllegalStateException(f"Duplicate key: {key!r}")`. Message unchanged, so it still names the colliding key per the spec.
- [x] 3.2 Confirm `to_map` is the only `ValueError` raise in `collector.py` that the story touches: `grep -n "raise ValueError" src/snakestream/collector.py` is empty afterwards.

## 4. Tests at the named sites only

- [x] 4.1 `tests/test_sink.py`: change the `Counter` import (line 4) to `Box`, and the four construction sites at lines 277-278, 304 and 326-327 to `Box(0)` / `Box(10)`.
- [x] 4.2 `tests/test_sink.py`: rewrite `test_counter_starts_at_zero_and_instances_are_independent` for `Box` — instances are independent, and `Box(7).value == 7` (line 336). The zero-default assertions go with the deleted default; rename the test accordingly.
- [x] 4.3 `tests/test_to_map.py`: change `pytest.raises(ValueError)` at line 47 to `pytest.raises(IllegalStateException)`, add the import, and rename `test_to_map_duplicate_key_without_merge_function_raises_value_error` to say `illegal_state_exception`.
- [x] 4.4 **Tripwire check.** `git diff --stat -- tests/` names exactly `tests/test_sink.py` and `tests/test_to_map.py`. Any third test file means the change went wider than the story — stop and flag it rather than absorbing it.

## 5. Docs

- [x] 5.1 `README.md` line 158: the `to_map` collector-table row says `ValueError`; change it to `IllegalStateException`.
- [x] 5.2 `README.md`: add a `0.3.5 -> next` migration-log entry for the `to_map` exception-type change — states the new type, that it is loud for `except ValueError` and silent for a bare `except`, that a `merge_function` call site is unaffected, and that it matches Java's `Collectors.toMap`. Reference `openspec/changes/tidy-collector-containers`.
- [x] 5.3 Leave the historical `redesign-collector-shape` entry (line 173) that mentions `to_map`'s duplicate-key `ValueError` unedited — it records what was true then. Verify it is untouched in the diff.

## 6. Verify

- [x] 6.1 `uv run pytest` — full suite green.
- [x] 6.2 `uv run pytest --cov-fail-under=98` — coverage at or above where it started (98.05% at last measure). A drop means a container branch lost a test, not that the gate is wrong.
- [x] 6.3 `uv run ruff check .` and `uv run ruff format --check .` clean.
- [x] 6.4 `uv run ty check src` clean — this is what catches a mistyped dataclass field.
- [x] 6.5 `openspec validate tidy-collector-containers --strict` passes.
- [x] 6.6 Clean-interpreter `python -c "import snakestream"` — rules out an import cycle from `collector.py`'s new `exception` import.
- [x] 6.7 Report the `src/` line-count delta for `collector.py` and `sink.py`; the story's claim is ~90 lines of boilerplate removed.

## 7. Roadmap

- [x] 7.1 Move story 6 out of **Now** into **Done** in `roadmap.md`, with the figures and decisions this change actually produced. **Now** becomes empty and the 2026-08-25 batch is closed; say so, and note that **Next** needs a refill.
