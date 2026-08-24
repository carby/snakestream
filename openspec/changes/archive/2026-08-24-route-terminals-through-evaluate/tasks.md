## 1. Implement

- [x] 1.1 Add an optional `executor: Executor | None = None` parameter to
      `Stream._evaluate()` (`stream.py:112-116`); body becomes
      `return await (executor or self._executor).value(self._chain, self._stream, terminal)`,
      after the existing `self._check_not_consumed()` call. Keep the docstring
      accurate: still "the one place a stream's execution mode is consulted",
      now naming the override parameter.
- [x] 1.2 Rewrite `for_each_ordered()` (`stream.py:292-294`) to
      `await self._evaluate(_ForEachSink(consumer), SEQUENTIAL)`, removing its
      hand-rolled `self._check_not_consumed()` + `SEQUENTIAL.value(...)` call.
- [x] 1.3 Rewrite `find_first()`'s tail (`stream.py:300-305`) to
      `await self._evaluate(_FindSink(), SEQUENTIAL)` when ordered, keeping the
      existing `is_ordered()` short-circuit to `find_any()` unchanged.

## 2. Spec wording check

- [x] 2.1 Re-read `openspec/specs/stream-find-first/spec.md` lines ~31-42
      ("achieve this by naming the sequential executor explicitly for its own
      drive") against the new call shape. If it still reads correctly with
      `SEQUENTIAL` passed as an `_evaluate()` argument, leave it as is. If it
      reads as naming the old call shape, edit the spec directly (not a
      delta — no requirement is changing).
      Checked: the wording names no call shape, only "naming the sequential
      executor explicitly for that drive" — `SEQUENTIAL` passed as
      `_evaluate()`'s second argument still satisfies this verbatim. Left
      unchanged.

## 3. Verify

- [x] 3.1 Run `uv run pytest` — full suite must pass with **no test file
      edited** (this batch's tripwire). 535 passed, only `stream.py` in the
      diff.
- [x] 3.2 Run `uv run ruff check .` and `uv run ruff format --check .`. Both
      pass.
- [x] 3.3 Run `uv run ty check src`. Passes.
- [x] 3.4 Run `openspec validate --strict` (skip_specs: true, so this checks
      the proposal/tasks only). Valid.
- [x] 3.5 Confirm no other call site still spells out
      `self._chain, self._stream` directly (grep `stream.py` for
      `self._stream` outside `_evaluate()` and `__init__`/derive methods) —
      `for_each_ordered()` and `find_first()` were the only two. Confirmed via
      grep: only `__init__`, `_derive`, `_compose`, `_evaluate`,
      `_derive_executor` reference `self._stream` now.
