## 1. Move the class

- [x] 1.1 Delete `Box` (the `@dataclass(slots=True)` at `src/snakestream/sink.py:40-46`) from `sink.py` and verify no name in `sink.py` still references it (`grep -n "Box" src/snakestream/sink.py` returns nothing).
- [x] 1.2 Add the same class to `src/snakestream/collectors.py` as `_Box`, unchanged in fields and semantics (`value: Any = None`, `@dataclass(slots=True)`), placed with the nine existing private containers, and verify the docstring still describes a mutable single-value container with no protocol claims.
- [x] 1.3 Drop `Box` from `collectors.py`'s `from snakestream.sink import UNSET, Box, unseeded` line (leaving `UNSET, unseeded`) and rewrite `counting()`'s four references (`_accumulate`'s annotation, `_combine`'s three, `_finish`'s one, and the `lambda: Box(0)` supplier) to `_Box`; verify `grep -n "\bBox\b" src/snakestream/collectors.py` matches only `_Box` occurrences.
- [x] 1.4 Verify `uv run ty check src` passes and `uv run ruff check . && uv run ruff format --check .` is clean.

## 2. Correct the stale prose

- [x] 2.1 Update `src/snakestream/terminals.py:20-22` (`CountSink`'s docstring: "A plain int, not a `Box`...") to name `_Box` in `collectors.py`, keeping the explanation of why this sink owns its container exclusively; verify by reading the rendered docstring that it points at the class's new home.
- [x] 2.2 Update `src/snakestream/ops.py:204` (`LimitOp`/`SkipOp` state: "Kept out of `Box` (`sink.py`), which collectors also build per composition...") to name `_Box` in `collectors.py`; verify the sentence still reads as the reason the counter carries a lock and the container does not.
- [x] 2.3 Re-read `sink.py`'s `UNSET` placement comment (`src/snakestream/sink.py:23-26`) and correct it only where it is wrong about `Box`; verify that the sentence about `collector.py` as a caller is left untouched, since rewriting it belongs to the remaining `sink-sentinel-placement` item.
- [x] 2.4 Update `tests/test_fork_join.py:209`'s comment ("explains why `Box`, elsewhere in this codebase, correctly has none") to name `_Box`; verify no `src/` or `tests/` comment still points at `Box` in `sink.py` (`grep -rn "Box" src tests | grep sink` is empty).

## 3. Follow the move in the tests

- [x] 3.1 Move `tests/test_sink.py`'s `Box` usages (import at line 4, and lines 277-278, 304, 326-327, 336, 371-372) to import `_Box` from `snakestream.collectors`, or relocate the `Box(7).value == 7` assertion to `tests/test_collectors.py` if that reads better beside the other container tests; verify `uv run pytest tests/test_sink.py tests/test_collectors.py` passes. (No `tests/test_collectors.py` exists; relocated the identity assertion to `tests/test_counting.py`, beside `counting()`'s own tests, since that is `_Box`'s only caller. Rest of the usages moved in place to `_Box` imported from `snakestream.collectors`.)
- [x] 3.2 Verify `uv run pytest tests/test_name_visibility.py` is green with no edit to that test — a red result means the rename was done wrong, not that the check needs adjusting.

## 4. Verify the whole change

- [x] 4.1 Run `uv run pytest --cov-fail-under=98` and verify the full suite passes at the coverage gate, confirming no behaviour changed.
- [x] 4.2 Confirm no README Migration entry is owed by verifying `Box`/`_Box` is not exported from `src/snakestream/__init__.py` before or after (`grep -n "Box" src/snakestream/__init__.py` is empty).
