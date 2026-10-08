+++
id = "retire-parallel-stream-name"
title = "Retired the `ParallelStream` name from the specs and docstrings"
filed = 2026-08-24
closed = 2026-08-24
outcome = "shipped"
+++

**Retired the `ParallelStream` name from the specs and docstrings**
(2026-08-24). `replace-parallel-stream-with-executor` deleted the class on
2026-08-21 but not the name: two requirements whose deltas were never written
or were missed by a truncated scan, ten spec `## Purpose` sections (a delta
cannot touch Purpose — OpenSpec ignores `MODIFIED` blocks against it, so
these needed direct edits), five docstrings in `sink.py` and
`callable_dispatch.py`, and four scenario titles kept back because a
`MODIFIED` block may not drop a scenario name the main spec still has.

No behaviour gap anywhere in it — every described behaviour was correct and
covered throughout — which is what made it worth one pass rather than a leak
across several commits: readability debt of the misleading kind, where a
reader grepping for `ParallelStream` found specs and docstrings promising a
class the codebase no longer had. `grep -rn ParallelStream openspec/specs/
src/` now returns nothing. Full suite green with **no test file edited**.
Out of scope deliberately, and still true today: test-file comments and
section headers, and the README migration-log entry that has to name the
retired class to explain what was retired. See
`openspec/changes/archive/2026-08-24-retire-parallelstream-name`.
