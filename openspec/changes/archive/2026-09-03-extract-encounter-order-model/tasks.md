## 1. Baseline

- [x] 1.1 Record the green baseline so any later failure is attributable: `uv run pytest` passes, and note both the test count (997 collected as of 2026-09-03) and the coverage figure for comparison in task 6.
- [x] 1.2 Record the per-file coverage rows for `sink.py` and `execution.py` from that run. Design's risk section expects them to move and the total not to; without the before-figures that cannot be checked.
- [x] 1.3 Confirm the move set is exactly four symbols and nothing else references them by module path: `grep -rn "Ordering\|OrderDemand\|is_ordered\|_split_point" src/ tests/ CLAUDE.md README.md` — every hit must be one of the call sites design's Context enumerates, a test import, or prose. A hit anywhere else widens scope and should be raised before continuing.

## 2. The new module

- [x] 2.1 Create `src/snakestream/ordering.py` with `from __future__ import annotations`, a `TYPE_CHECKING` import of `Op` from `snakestream.sink` (decision 2), and a module docstring stating: what the module holds (the encounter-order model — the vocabulary, the fold and the split search), the op/terminal pairing the two enum docstrings state from opposite ends, and the constraint that it reads ops *structurally* and imports `Op` for typing only, so the `sink -> ordering` edge stays one-directional. Verify the file imports cleanly on its own: `uv run python -c "import snakestream.ordering"`.
- [x] 2.2 Move `Ordering` into it from `sink.py`, docstring verbatim (decision 6). Verify by `git diff` that the class body and docstring are character-identical to the removed text.
- [x] 2.3 Move `OrderDemand` into it from `execution.py`, docstring verbatim. Place it immediately after `Ordering`, so the two enums the docstrings pair are adjacent in the file.
- [x] 2.4 Move `is_ordered()` into it from `sink.py`. Its docstring's closing paragraph is one of the three owed prose edits (decision 6, item 1): the clause *"`Op` and `Ordering` both live here already"* is false after this change. Restate that paragraph as why the fold is a free function over a chain rather than a `Stream` method — the part that survives — and keep every other paragraph verbatim.
- [x] 2.5 Move `_split_point()` into it from `execution.py`, docstring verbatim, placed last so the file reads vocabulary → fold → search. Verify it references only names now local to this module plus the `Op` annotation.
- [x] 2.6 Confirm the module imports nothing at runtime from anywhere in the package: `grep -n "^from\|^import" src/snakestream/ordering.py` shows only `__future__`, `enum`, `typing`, and the `TYPE_CHECKING` block. Anything else contradicts decision 1's claim that the group has no dependencies.

## 3. `sink.py`

- [x] 3.1 Delete `Ordering` and `is_ordered()` and add `from snakestream.ordering import Ordering` (runtime — `Op.ordering`'s `ClassVar` default needs the member). Verify `uv run python -c "import snakestream"` succeeds, which is what proves the edge is not a cycle.
- [x] 3.2 Confirm `Op.ordering` and `Op.order_sensitive` are still declared on `Op`, unchanged, with their existing docstring paragraphs intact (decision 3).
- [x] 3.3 Update the module docstring: it currently lists what the module contains, and the ordering characteristic is no longer part of that (decision 6, item 2). Point at `ordering.py` for the vocabulary the `Op` ClassVars are written in.
- [x] 3.4 Verify nothing else in `sink.py` referenced the two moved names: `grep -n "Ordering\|is_ordered" src/snakestream/sink.py` returns only the import and the `Op.ordering` declaration.

## 4. `execution.py`, `ops.py`, `stream.py`

- [x] 4.1 In `execution.py`: delete `OrderDemand` and `_split_point()`, and import both from `snakestream.ordering` alongside the existing `snakestream.sink` import. Verify `race_through()`, `_run_ordered_tail()`, `Executor`, `Sequential` and `Racing` are otherwise untouched — `git diff src/snakestream/execution.py` shows only the import block, the two deletions and the docstring edit in 4.2.
- [x] 4.2 Update `execution.py`'s module docstring (decision 6, item 3): it still names `_split_point()` as what `race_through()` consults, now naming its module. Nothing else in that docstring changes — the four primitives, the barrier description and the executor asymmetry are all still true of this file.
- [x] 4.3 In `ops.py`: change `Ordering` to import from `snakestream.ordering`, leaving the rest of the `snakestream.sink` import list as it is. Verify `_SortedOp.ordering = Ordering.SET` and `_UnorderedOp.ordering = Ordering.CLEAR` are unchanged.
- [x] 4.4 In `stream.py`: `is_ordered` moves to the `snakestream.ordering` import and `OrderDemand` moves off the `snakestream.execution` import (which keeps `PROCESSES`, `RACING`, `SEQUENTIAL`, `Executor`). Verify every `OrderDemand.*` argument at the eleven call sites is character-identical to before — `git diff src/snakestream/stream.py` shows import lines only.
- [x] 4.5 Run `uv run python -c "import snakestream; import snakestream.ordering, snakestream.ops, snakestream.execution, snakestream.stream"` in a fresh interpreter, then again with the imports in reverse order. A cycle that only bites under one import order is the specific failure decision 2 is exposed to.

## 5. Tests and docs

- [x] 5.1 Update the three test import lines and nothing else: `tests/test_op_protocol.py` (`Ordering`, `is_ordered` — the other names on that line stay on `snakestream.sink`), `tests/test_unordered.py` (`OrderDemand`, `_split_point`), `tests/test_racing_encounter_order.py` (`OrderDemand` only — `PROCESSES`, `_Window`, `_guarded`, `_in_flight`, `_release_in_order` all stay on `snakestream.execution`, per decision 4). Verify with `git diff tests/` showing import lines only.
- [x] 5.2 Verify the regression claim design's risk section names — the test edits are in scope, so what is checked is their shape, not their absence: `git diff --stat tests/` touches exactly three files, `uv run pytest` collects 997 tests, and no test name or body changed.
- [x] 5.3 Update `CLAUDE.md`'s "The ordering barrier" section to name `ordering.py` as the model's home, and fix the two location claims that go stale: the `_is_ordered()` paragraph (the fold's home) and the `_split_point()` description. Verify by re-reading the section as someone who has not seen the code — it must be possible to open one file and find all four symbols.
- [x] 5.4 Confirm no README edit is owed: no public API is added, renamed or removed, so the parity tables are unaffected and the Migration log takes no entry. Verify `git diff --stat` shows no README change and no `src/snakestream/__init__.py` change.

## 6. Gates

- [x] 6.1 `uv run ruff check .` and `uv run ruff format --check .` both pass, including on this change's markdown files (the house has tripped on markdown fences before).
- [x] 6.2 `uv run pytest` passes with the count from task 1.1, and `uv run pytest --cov-fail-under=98` passes. Total coverage must not fall: no statement is added or removed, only relocated.
- [x] 6.3 Compare per-file coverage against task 1.2's figures: `sink.py` and `execution.py` lose exactly the statements that moved, `ordering.py` gains exactly those, and the missed count is 0 in all three. A missed statement in `ordering.py` means something arrived uncovered, which cannot happen in a pure move and would mean a body changed.
- [x] 6.4 `uv run ty check src` passes. Watch specifically for the `TYPE_CHECKING` `Op` annotation in `ordering.py` — if `ty` resolves it differently from `ruff`, that is design's second risk and the recorded fallback is decision 2's `Protocol` alternative.
- [x] 6.5 Verify the zero-behaviour-delta claim directly rather than only through the suite: `git diff src/` contains no change to any function *body* except the three enumerated docstring edits (decision 6) — every other line is a move, an import, or a deletion.
- [x] 6.6 Do **not** benchmark this change, per decision 5. If a reviewer asks for a figure, point at that decision: nothing is called differently, so a ns/element number would measure harness noise and banking one would imply a gate this change is not subject to.

## 7. At archive

- [x] 7.1 Confirm `skip_specs: true` still holds at archive time — no spec under `openspec/specs/` names a module path for any of the four symbols, so no delta is owed and none was written. Re-verify with `grep -rn "sink\.py\|execution\.py\|ordering\.py" openspec/specs/`.
- [x] 7.2 Add the roadmap **Done** entry. It should state what moved and why (concern over import topology), that no behaviour changed and no benchmark was owed, and record the two rejected consolidations from decision 1 — into `sink.py` (worsens the same problem) and into `execution.py` (an actual cycle) — so neither is re-derived. Note also that this is the first entry in **Done** that is a module-boundary change rather than a duplication call.
- [x] 7.3 Record the follow-on in the roadmap's **Now**, not as scaffolded work: `_UNSET`, `_unseeded()` and `Box` sit in `sink.py` on the same import-topology reasoning this change rejected, and the same diagnosis applies. State explicitly that the diagnosis transfers and the decision does not — that placement is its own call, and it is unclaimed.
