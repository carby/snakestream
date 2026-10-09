## Context

See `proposal.md` - Why. CI today runs `code_check` on `3.14` and `3.14t`, with
`ty`, `pip-audit` and the coverage gate guarded to `3.14`; `install_smoke_test`
and `deliver.yml` run `3.14` alone. `actions/setup-uv` is unpinned, so CI gets
the newest uv, and the matrix value `"3.15"` asks it for the newest available
3.15 interpreter.

## Goals / Non-Goals

**Goals:**

- Every supported version is tested on both builds; every packaging check runs on
  every supported version.
- The single-leg checks have one unambiguous home that moves forward on its own
  as versions are added.

**Non-Goals:**

- Raising `requires-python`, ruff's `target-version` or `.readthedocs.yml`'s
  interpreter. Each either drops 3.14 or is unrelated to what CI verifies.
- Testing a 3.15-only feature. The library uses none.

## Decisions

1. **Single-leg checks move to the newest GIL-enabled leg (`3.15`).** The
   alternative was keeping them on the floor (`3.14`). The newest version is
   where something new happens. pip-audit resolves the environment that version
   produces, and coverage may count branches differently under a new
   interpreter's tracing (`sys.monitoring`), so the 98% gate should hold where
   that risk is. `CLAUDE.md` already says the gate runs on the newest
   interpreter.
   - **What moving `ty` does not do.** The repo has no `[tool.ty]` python-version
     pin, so ty takes its target from the `requires-python` floor and keeps
     checking 3.14 semantics. Moving it is a placement choice, and adds no 3.15
     type coverage.

2. **`install_smoke_test` gets `3.15`, but not `3.15t`.** The spec requires the
   first. The second was declined for `3.14t` in `add-free-threaded-ci-leg`
   (pure-Python `py3-none-any` wheel, empty `project.dependencies`), and both
   premises still hold. They are re-verified as a task rather than assumed.

3. **`deliver.yml` runs `3.14` and `3.15`.** It is the post-merge re-check and
   publishes nothing. Giving it the same GIL-enabled set as the smoke test keeps
   one rule ("every supported version, GIL build") instead of two. Adding
   free-threaded legs there would duplicate `code_check`, which already gates
   the merge.

4. **No interpreter-version conditionals in the library or tests.** This follows
   the existing build-conditional rule. If 3.15 needs a branch, that's a defect
   to report, not a branch to add.

## Risks / Trade-offs

- [3.15.0 final isn't yet available through uv. python-build-standalone offers
  `3.15.0rc3` on 2026-10-09] → The legs run on rc3 until it is, and the matrix
  value moves to final with no workflow edit. The roadmap item stays open until
  a CI run's setup-uv log shows `3.15.0` final on both 3.15 legs.
- [A dev or test dependency ships no `cp315t` wheel] → `uv.lock` already carries
  `cp315t` wheels for `coverage`, the only compiled dependency. The 3.15t leg
  fails loudly if that changes.
- [CI time: four `code_check` legs instead of two] → They run in parallel
  (`fail-fast: false`), so wall-clock time is unchanged. The added cost is
  runner minutes only.

## Migration Plan

No caller-visible change and no CHANGELOG entry. To roll back, revert the
workflow matrices.
