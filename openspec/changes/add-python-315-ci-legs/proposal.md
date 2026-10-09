## Why

`requires-python = ">=3.14"` already admits CPython 3.15, which is released
(`Python-3.15.0.tgz` is on python.org as of 2026-10-09). Yet CI exercises only
3.14 and 3.14t, so the distribution claims an interpreter it has never been
tested on. The free-threaded build is the most exposed: `.parallel()`'s real CPU
parallelism rests on it, and the fork/join executor's thread dispatch is exactly
what a change to the free-threaded runtime could break.

This is roadmap item `support-python-315`.

## What Changes

- `code_check` gains `3.15` and `3.15t` legs, beside `3.14` and `3.14t`. Lint,
  format check and the test suite run on all four.
- `ty`, `pip-audit` and the coverage threshold stay single-leg, but move from
  `3.14` to `3.15`: the GIL-enabled leg of the **newest** supported version,
  which is what `CLAUDE.md` already says the coverage gate runs on. With two
  GIL-enabled legs, "the GIL-enabled leg" in the spec no longer names one.
- `install_smoke_test` gains a `3.15` leg. Its spec already requires one leg per
  supported version, and 3.15 is supported. No `3.15t` leg, for the reason
  `add-free-threaded-ci-leg` declined `3.14t`: the wheel is `py3-none-any` and
  `project.dependencies` is empty, so it would install a byte-identical
  artifact.
- `deliver.yml` (the post-merge re-check) runs on `3.14` and `3.15`, the same
  GIL-enabled set as the smoke test, with its `pip-audit` gate moved to `3.15`.
- `CLAUDE.md` describes the four legs and gains a local `3.15t` command.

**No change to `src/`**, and no change to `requires-python` or ruff's
`target-version`. Raising either would drop 3.14, which is a separate decision.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `free-threaded-support`: the free-threaded leg is required for each supported
  interpreter version, not "the" supported interpreter. The single-leg checks
  are pinned to the GIL-enabled leg of the newest supported version.
- `install-smoke-test`: the supported set named in the requirement becomes 3.14
  and 3.15, two legs.

## Impact

- `.github/workflows/check.yml`: both matrices, three `if:` conditions, one
  comment
- `.github/workflows/deliver.yml`: matrix and one `if:` condition
- `CLAUDE.md`
- `openspec/specs/free-threaded-support`, `openspec/specs/install-smoke-test`
- **Nothing under `src/`.**

The gate the roadmap item sets, "3.15.0 final installable through uv", is
**not yet met**. On 2026-10-09 the newest uv (0.12.24) offers only
`cpython-3.15.0rc3`, because python-build-standalone hasn't yet published the
final release. The matrix entry `"3.15"` resolves to the newest available 3.15
build, so these legs run on rc3 today and move to 3.15.0 without a workflow
edit. The roadmap item stays open until a CI run is confirmed on the final
release.
