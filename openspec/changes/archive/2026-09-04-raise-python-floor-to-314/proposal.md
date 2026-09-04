## Why

Last of the four sequenced floor raises. See the three archived predecessors
(`2026-09-04-raise-python-floor-to-311`, `…-to-312`, `…-to-313`) for the
sequence. With this change the supported set is **3.14 only**, which is what the
sequence was for: free-threading (PEP 779) is officially supported as of 3.14,
and it is the substrate the racing-executor replacement would be built on.

**This change is the bump and nothing else.** No `spliterator()`, no
free-threaded CI leg, no executor work — those are the next plan's subject, and
this one deliberately arrives at the floor without spending anything it unlocks.

The 3.14 feature it takes is **PEP 649 (deferred evaluation of annotations)**,
and again only as a consumer: annotations are lazily evaluated by default, so
the 17 quoted forward references left in the tree can be unquoted. Thirteen of
those are in `comparator.py`, the one module in `src/snakestream` that never
took `from __future__ import annotations`, and quoting is the workaround it has
been carrying instead.

## What Changes

- **BREAKING**: `requires-python` moves from `>=3.13` to `>=3.14`. Installing on
  3.13 now fails at resolution. As in the previous step, this is the **only**
  observable break — no runtime, typing, or introspection behaviour changes.
- 17 `UP037` findings are fixed (quotes removed): 13 in
  `src/snakestream/comparator.py`, 4 across `tests/test_execution_model.py`,
  `test_racing_delivery_order.py` and `test_racing_encounter_order.py`. All
  ruff-autofixable.
- Both CI matrices collapse to a single leg, `["3.14"]`.
- **The three `if: matrix.python-version == '3.14'` conditionals are removed**
  from `check.yml`. They gated `ty`, `pip-audit` and the coverage threshold to
  the newest leg; with one leg they are always true, and each carries a comment
  justifying a restriction that no longer restricts anything. The steps stay;
  only the conditions and their now-false comments go.
- `.readthedocs.yml`'s `python: version: "3.13"` is raised to `"3.14"`, since it
  is otherwise pinned *below* the floor. See Impact — that file has a larger
  problem this change deliberately does not take on.
- `ruff`'s `target-version` moves to `py314`; `CLAUDE.md`'s matrix line is
  corrected; a README Migration entry records the dropped interpreter.

**Explicitly not taken:**

- **Removing `from __future__ import annotations`** from the nine modules that
  carry it. Ruff does not flag it at `py314` (verified: zero findings), and it
  is not redundant — PEP 563 (the future import) makes annotations *strings*
  while PEP 649 makes them *lazily evaluated objects*, so removing it changes
  what `__annotations__` and `get_type_hints()` return. That is a runtime
  introspection break of the same kind the 3.12 step took for `type.py`'s
  aliases, and it deserves its own change rather than riding along on a bump.
- **Anything free-threading.** No `3.14t` matrix leg, no `spliterator()`, no
  executor change. Next plan.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `install-smoke-test`: the stated matrix moves from 3.13–3.14 to 3.14 alone.

**Deliberately not modified.** `static-type-checking` requires the checker to
run "on at least one Python version in the build matrix" and `lint-rule-selection`
requires the widened selection "on every matrix leg" — both remain literally true
of a one-leg matrix, so removing the conditionals changes no requirement.
`branch-coverage-gate` names no interpreter at all.

## Impact

- `pyproject.toml` — `requires-python`, `[tool.ruff] target-version`
- `.github/workflows/check.yml` — both matrices, plus three `if:` conditionals
  and the comments explaining them
- `src/snakestream/comparator.py` — 13 annotations unquoted
- `tests/` — 4 annotations unquoted, in three files
- `.readthedocs.yml` — the Python pin
- `CLAUDE.md`, `README.md`, `openspec/specs/install-smoke-test/spec.md`

**Reported, not fixed: `.readthedocs.yml` is dead.** It declares
`sphinx.configuration: docs/conf.py` and installs `docs/requirements.txt`, and
there is no `docs/` directory in the repository — so the documentation build it
describes cannot be running. The pin is raised here only to stop the file
contradicting `requires-python`; whether the file should be revived or deleted is
a real question and is out of scope for a version bump. Flagged so it is a
decision rather than an oversight.
