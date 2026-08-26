## 1. Turn the gate on for `tests/`

- [x] 1.1 Add `PT` to `[tool.ruff.lint] select` in `pyproject.toml`, keeping the families already there.
- [x] 1.2 Replace the `per-file-ignores` entry for `tests/**` with `["PLR2004"]`, and rewrite its comment to state the reason for that one rule (test literals are the test's data) rather than the old family list.
- [x] 1.3 Confirm the starting position: `uv run ruff check .` reports the expected 65 findings, all under `tests/`, and `uv run ruff check src/` is still clean.

## 2. The correctness fixes (design Decisions 2, 3)

- [x] 2.1 Replace `assert False` with `pytest.fail(<message>)` at all 11 sites: `test_filter.py:24,83`; `test_flat_map.py:30,51,106`; `test_integration.py:20`; `test_map.py:25,43`; `test_of.py:52,71,90`. Give each a message naming what did not happen (e.g. the stream failed to terminate), since the bare `assert False` communicated only through its position in the `else:`.
- [x] 2.2 Verify each of those 11 sits in an `else:` after `except StopAsyncIteration` and that `pytest` is already imported in the file; add the import where it is not.
- [x] 2.3 Add `match="boom"` to the three `pytest.raises(ValueError)` calls in `test_exception.py:14,25,36`, so each asserts it caught its own callback's `ValueError` (design Decision 3 — do **not** narrow these to `StreamException`; the exception under test is deliberately not a library one).
- [x] 2.4 Confirm `uv run ruff check tests/ --select=B011,PT015,PT011` is clean.

## 3. The safe auto-fixes (design Decision 6)

- [x] 3.1 Run `uv run ruff check tests/ --fix` (safe fixes only — **not** `--unsafe-fixes`) to clear the 22 `SIM300` yoda conditions (`test_of.py` x15, `test_close.py` x2, `test_parallel.py` x2, `test_sequential.py` x2, `test_collect.py` x1), 2 `RET505` (`test_sorted.py:41,63`) and 1 `PLR1711` (`test_peek.py:43`).
- [x] 3.2 Read the resulting diff and confirm every hunk is an operand reorder or a dead-branch removal — no comparison's truth value changed, no assertion's subject changed.

## 4. The remaining hand fixes

- [x] 4.1 `PT006` (`test_pipeline_immutability.py:41,48,58`): pass the parametrize names as a tuple rather than a comma-joined string.
- [x] 4.2 `PT018` (`test_summarizing.py:40,41,42`): split each composite assertion into separate asserts, so a failure reports which conjunct failed.
- [x] 4.3 `PLW0108` (`test_flat_map.py:18,35`; `test_limit.py:84`; `test_pipeline_immutability.py:15`): inline the wrapped callable where the lambda only forwards its argument. Check each is a true forward and not a signature adapter before removing it.
- [x] 4.4 `C417` (`test_map.py:66,79`): rewrite the `map()` calls as list comprehensions.
- [x] 4.5 `SIM401` (`test_sink.py:107`): use `state_map.get(self._op, [0])` in place of the `if` block.
- [x] 4.6 `PLW1510` (`test_static_typing.py:11`): pass `check=False` explicitly to `subprocess.run` — the callers assert on `returncode` and a non-zero exit is the expected outcome, so the value stays as it is and only the implicitness is fixed (design Decision 5).
- [x] 4.7 `PT012` (`test_exception_hierarchy.py:28`): add `# noqa: PT012` with the reason — the `try`/`except ValueError` inside `pytest.raises(StreamException)` is the mechanism the test exists to demonstrate, so splitting the block would delete what is being tested (design Decision 4). This is the change's only inline suppression.

## 5. Verification

- [x] 5.1 `uv run ruff check .` clean over the whole tree.
- [x] 5.2 `uv run ruff format --check .` clean — re-run `ruff format .` if the rewrites disturbed layout.
- [x] 5.3 `uv run pytest` reports **567 passed**, the same count as before the change. A different number means a rewrite changed what runs, not just how it reads.
- [x] 5.4 `uv run pytest --cov-fail-under=98` still passes, and `uv run ty check src` is still clean.
- [x] 5.5 Confirm `git diff --stat` touches only `pyproject.toml` and files under `tests/` — no `src/` hunk.
- [x] 5.6 Read the full diff for weakened assertions: every hunk must be the same assertion restated or a strictly stronger one (design, Non-Goals).
- [x] 5.7 Check what the guard rewrite actually buys, against the real suite rather than by argument. Under default pytest, `-O` changes nothing (pytest rewrites assertions in test modules, so `assert False` already fires) -- so compare under `-O --assert=plain` instead, against a baseline worktree at HEAD: before, 37 pass vacuously; after, 10 fail reporting `stream should be exhausted`. Record the correction in design Decision 2.
- [x] 5.8 Update `roadmap.md`: move both **Next** items into **Done** with the corrected figures (283 not 61; `PT011` was `raises(ValueError)` on a user exception, not `raises(Exception)` to be narrowed to `StreamException`), and note that `PLR2004` is now the single named exemption.
