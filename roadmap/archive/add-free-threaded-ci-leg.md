+++
id = "add-free-threaded-ci-leg"
title = "CI gains a free-threaded `3.14t` leg (`add-free-threaded-ci-leg`)"
filed = 2026-09-04
closed = 2026-09-04
outcome = "shipped"
shipped_as = "add-free-threaded-ci-leg"
+++

**`add-free-threaded-ci-leg`** (2026-09-04) — CI gains a `3.14t` leg on
`code_check`, and the audit that made it safe to build on. Three properties
verified and promoted from observation to spec requirement: no module-level
mutable state anywhere in `src/`, every `ClassVar` an immutable declaration,
and per-composition dispatch state that cannot leak. The suite passed on the
free-threaded build **unmodified**, which is what made the sequence's premise
credible before anything depended on it.

`install_smoke_test` deliberately did **not** get the leg. The first draft
said it should, reasoning that wheel tags differ and a dependency might ship
no free-threaded wheel; both were checked and neither holds — `uv build
--wheel` produces `py3-none-any` and `project.dependencies` is empty, so the
leg would install a byte-identical artifact twice.

The obligation it handed forward, and the reason it went first:
`execution.py`'s two `asyncio.Lock` sites were correct only because one event
loop owned every branch, and `asyncio.Lock` does not synchronise across
threads. Fork/join discharged it with `threading.Lock`-guarded containers in
`ops.py`.
