+++
id = "derive-executor-argument"
title = "`Stream._derive()` gains an optional `executor` argument"
filed = 2026-08-27
closed = 2026-08-27
outcome = "shipped"
+++

**`Stream._derive()` gains an optional `executor` argument, collapsing
`sequential()`/`parallel()` to one line each** (2026-08-27). `_derive()`'s
docstring claimed it derives "under the same executor", but its two mode-switch
callers falsified that by hand — `derived = self._derive(); derived._executor =
SEQUENTIAL; return derived` — the only place in `stream.py` where a method
wrote a private attribute of an object it did not own. The fix is one
parameter: `_derive(op=None, executor=None)`, with
`new_stream._executor = executor or self._executor` replacing the
unconditional assignment, so both derivation rules (chain and executor) live
in the one method that already advertises itself as their home.
`sequential()`/`parallel()` become `return self._derive(executor=SEQUENTIAL)`
/ `return self._derive(executor=RACING)`. Pure refactor: no behaviour change,
no test edited, `--cov-fail-under=98` passes at 98.30% (691 passed), `ruff`,
`ruff format --check`, and `ty check src` all clean. Fourth pass over this
cluster; its proposal records why it is not a revert of
`collapse-derive-wrappers`. Also retired that entry's `await`-in-`_derive()`
tripwire (below) — `executor or self._executor` restores the assign-once
property the tripwire existed to guard — and updated the CLAUDE.md paragraph
that described the old two-statement mode-switch body. No delta specs:
`.openspec.yaml` set `skip_specs: true`, no capability names `_derive()`. See
`openspec/changes/archive/2026-08-27-unify-derive-signature`.
