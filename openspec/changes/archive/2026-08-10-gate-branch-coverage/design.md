## Context

`pyproject.toml` sets `[tool.coverage.run] branch = true`, so `coverage.py` already collects branch-arc data alongside line data. CI (`.github/workflows/check.yml`) runs `uv run pytest --cov-fail-under=98` only on the Python 3.14 leg — a deliberate choice (documented in a comment) because branch-arc measurement for `async for` loops differs across CPython versions and produces spurious failures on older interpreters.

The open question this change resolves: does `--cov-fail-under=98` (a `pytest-cov` flag, forwarded to `coverage.py`) actually gate on combined line+branch coverage, or only on line coverage, with `branch = true` silently doing nothing for enforcement purposes?

## Goals / Non-Goals

**Goals:**
- Establish, with evidence, whether the existing `--cov-fail-under=98` gate already reflects combined line+branch coverage.
- If it does not, add the minimum config change needed to make it so, without altering the 98% threshold or the single-Python-version enforcement strategy.
- Leave a trace (test and/or comment) so this doesn't need re-litigating later.

**Non-Goals:**
- Changing the 98% threshold value.
- Enforcing coverage on every matrix leg (the cross-version measurement issue is out of scope here).
- Introducing a new coverage tool or reporting format.

## Decisions

- **How to verify**: introduce a throwaway, deliberately-partial branch (an `if`/`else` where only one side is exercised by tests) in a scratch/local run of `coverage report`, confirm the percentage drops and `--cov-fail-under` fails, then revert the scratch code. This directly demonstrates whether branch misses affect the gate. `coverage.py`'s documented behavior is that with `branch = true`, the reported "percent covered" already combines statement and branch execution into one ratio — so `--cov-fail-under` should already be a combined gate. This step confirms that's true in this project's actual config rather than assuming it from documentation alone.
- **Where to encode the finding**: prefer a comment in `pyproject.toml` next to `branch = true` over a new CI step, since the mechanism (if already working) needs no code change — only a record of why no further action was taken. This keeps the change additive and avoids duplicating enforcement.
- **If a real gap is found**: the fallback is `[tool.coverage.report] fail_under = 98` (coverage-native) instead of the `pytest-cov` CLI flag, since `fail_under` in `[tool.coverage.report]` is unambiguously the combined-metric gate per coverage.py's own semantics. This would replace, not duplicate, the existing `--cov-fail-under` flag to avoid two sources of truth for the threshold.

## Risks / Trade-offs

- [Risk] A scratch/local verification step is manual and not repeatable in CI → Mitigation: if the verification confirms current behavior is correct, capture the reasoning in a comment; no ongoing manual step is required afterward.
- [Risk] Adding a regression test for an intentionally-uncovered branch could itself lower coverage or feel artificial → Mitigation: only add a regression test if verification actually finds a gap; otherwise skip it per the proposal's conditional wording.
