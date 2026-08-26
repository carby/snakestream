## Why

The previous change (`builtins-stdlib-and-lint-gate`, archived 2026-08-26)
widened the ruff selection but scoped it to `src/` with a `per-file-ignores`
entry, deliberately parking the `tests/` half as its own decision. Both items
it left in the roadmap's **Next** are that decision, and they are the same
edit: `PT011`'s three sites cannot be fixed without enabling `PT`, which is the
`tests/` question.

`tests/` is where a lint gate earns the most and is trusted the least. Two of
the findings go beyond style: eleven `assert False` guards that report nothing
when they fire and depend on pytest's assertion rewriting to fire at all, and
three `pytest.raises(ValueError)` blocks that pass on any `ValueError` from
anywhere in the pipeline rather than the one the test provoked.

**The roadmap's figures for this item were wrong, and measuring first changed
the shape of the change.** It recorded 61 findings for a trial set that omitted
`PLR`, `PLW`, `RET`, `PIE` and `FURB`; the real total under the selection now
in `pyproject.toml`, plus `PT`, is **283**. Of those, **218 are `PLR2004`**
alone. It also recorded `PT011`'s three sites as `pytest.raises(Exception)` to
be narrowed to `StreamException`; they are in fact `pytest.raises(ValueError)`,
and the exception under test is raised by a *user* callback to prove it
propagates — a library base would be exactly the wrong assertion.

## What Changes

- **`PLR2004` is exempted for `tests/` and only there.** All 218 sites are test
  data and assertions (`lambda x: x > 5`, `assert largest == 7`). Hoisting each
  compared literal into a named constant would make the tests read worse, not
  better. It stays enforced over `src/`, where it currently finds nothing.
- **Every other family now applies to `tests/`**, and `PT`
  (flake8-pytest-style) joins the selection. The `per-file-ignores` entry
  shrinks from eleven families to one rule.
- **The 65 remaining findings are fixed** (~54 distinct sites, since `B011` and
  `PT015` flag the same eleven):
  - **11 `assert False`** in `else:` branches after `try/except
    StopAsyncIteration` become `pytest.fail(...)`, each with a message. Two
    reasons, one of them narrower than this change first claimed: a bare
    `assert False` reports no message at all when it fires, and it survives
    `python -O` only because pytest rewrites assertions inside test modules.
    Turn rewriting off (`--assert=plain`) or move the guard into a helper
    module pytest does not rewrite -- the case pytest's own warning names --
    and the guard is stripped and the test passes silently. `pytest.fail()` is
    a call and depends on neither.
  - **3 `PT011`** `pytest.raises(ValueError)` gain `match=` so the test asserts
    it caught *its own* `ValueError("boom")` and not an unrelated one.
  - **22 `SIM300`** yoda conditions (`assert 4 == len(it)` -> `assert len(it) ==
    4`), auto-fixable.
  - **~13 small ones**: `PT006` (3), `PT018` (3), `C417` (2), `RET505` (2),
    `PLW0108` (4), `SIM401` (1), `PLR1711` (1), `PLW1510` (1), `PT012` (1).
- **The gate goes green over the whole tree**, so `ruff check .` — what CI
  already runs — enforces the same families everywhere except the one exempted
  rule.

## Capabilities

### New Capabilities
<!-- none: the lint gate capability already exists and this extends its scope -->

### Modified Capabilities
- `lint-rule-selection`: the gate's scope. Today it requires enforcement over
  `src/snakestream`; it must now cover the test suite too, with a stated,
  narrow exemption rather than a blanket per-path opt-out, and it must cover
  the pytest-specific family that only test files can trigger.

## Impact

- **Config:** `pyproject.toml` — `PT` added to `select`; the `per-file-ignores`
  entry for `tests/**` reduced from eleven families to `["PLR2004"]`.
- **Tests:** ~54 sites across the suite. **This change edits test files by
  design** — the inverse of the previous change, whose tripwire was that no
  test file be touched. No test's *assertions* weaken: the eleven `assert
  False` sites and the three `raises` blocks get strictly stronger, and the
  rest are rewrites of the same assertion.
- **Source:** none. `src/` already passes the widened selection and `PT` rules
  do not fire outside test files.
- **CI:** no workflow edit. `ruff check .` reads the config, exactly as with
  the previous widening.
- **Behaviour:** none. No library code changes; the suite must still report the
  same number of passing tests.
