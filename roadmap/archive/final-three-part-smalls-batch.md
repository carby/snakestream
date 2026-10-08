+++
id = "final-three-part-smalls-batch"
title = "Took the final three-part smalls batch"
filed = 2026-08-24
closed = 2026-08-24
outcome = "shipped"
+++

**Took the final three-part smalls batch: `unordered()`/`on_close()`
docstrings, the `PROCESSES` top-level export, and the dead `pylint`
pragmas in `collector.py`** (2026-08-24). The last item of the 2026-08-24
legibility batch, closing it out entirely.

**(a)** `unordered()` (`stream.py:151`) and `on_close()` (`stream.py:158`)
each gained a one-line docstring stating they mutate and return `self` by
design, unlike the eight derive-and-consume intermediate ops — pointing at
the `stream-ordering` spec and `pipeline-immutability` spec line 58
respectively, the requirements that already made this deliberate.

**(b)** `PROCESSES` is now exported from `snakestream/__init__.py`
(`from snakestream.execution import PROCESSES as PROCESSES`), so
`from snakestream import PROCESSES` works. Decided in favor of exporting
rather than narrowing README, matching how README already documented
`.parallel()`/`PROCESSES` as a stable public pair. New capability
requirement added to `stream-execution-model` covering the import path;
no README wording change was needed, and no existing top-level-exports
table needed touching (none exists). Covered by a new
`tests/test_package_exports.py`.

**Superseded by `name-by-visibility-not-underscore` (2026-09-03, below):**
the export is removed. It never was a tunable lever — `execution.py` binds
`RACING` from `PROCESSES` at import time, so assigning to the exported
name never changed the worker count — and the `stream-execution-model`
requirement this added is the one that change's spec delta removes.
`PROCESSES` keeps its name and value in `snakestream.execution`; only the
two import paths are gone.

**(c)** The four `# pylint: disable=missing-*-docstring` /
`# pylint: disable=invalid-name` pragmas at the top of `collector.py`
were confirmed dead (no `pylint` config or invocation anywhere in the
repo — only comment pragmas, here and in two unrelated test files left
out of scope) and deleted.

536 tests green (535 + the new export test) with **no existing test file
edited**; `ruff`, `ruff format --check`, `ty check src` and
`openspec validate --strict` all pass, 98% coverage. Off the per-element
path (docstrings are read not executed; the export and pragma removal are
import-time/lint-time only), so no benchmark gate applied. See
`openspec/changes/archive/2026-08-24-batch-small-fixes-2026-08-24`.
