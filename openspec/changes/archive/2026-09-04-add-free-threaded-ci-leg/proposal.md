## Why

The four floor raises are done and the floor is 3.14, which was never the point:
the point was **free-threading (PEP 779)**, officially supported as of 3.14, as
the substrate for a contiguous-splitting `spliterator()` and the retirement of
the racing executor. That work is now unblocked, and this change is the
foundation it stands on.

It is deliberately *not* the parallelism work. Before anything is built on
free-threading, two things should be true and neither is yet: CI should prove the
library is correct on a free-threaded interpreter, and the shared mutable state
the forking executor will have to reason about should be written down. This
change does those two things and changes no library behaviour at all.

The substrate was measured before this was proposed, and the figures belong in
the record rather than in a conversation. On a free-threaded 3.14.5 at 4 workers,
CPU-bound work in threads runs **2.6–3.0x** faster; on a GIL build the same code
gets **1.01x**, which is to say nothing. The roadmap's premise — that real
parallelism is worth wanting and that the interpreter was the obstacle — holds.

## What Changes

- The `code_check` CI matrix gains a `3.14t` (free-threaded) leg, alongside
  `3.14`. **`install_smoke_test` does not** — see below.
- The three steps whose conditionals were removed when the matrix collapsed to a
  single leg — `ty`, `pip-audit`, the coverage threshold — are gated again, now
  on `3.14`. With two legs there is once more a redundancy to avoid, and the
  original rationale applies unchanged: none of the three varies by interpreter
  build. This restores a distinction the 3.14 bump correctly removed when it was
  vacuous; it is not a revert of that decision.
- A new `free-threaded-support` capability records what CI now guarantees, and
  the thread-safety properties the library currently has, so the forking
  executor has a written baseline rather than an assumption.
- `CLAUDE.md`'s commands and matrix description gain the free-threaded leg.

**No change to `src/`.** No behaviour, no API, no dependency. Verified: the
existing 1000 tests pass on a free-threaded build unmodified.

## Capabilities

### New Capabilities

- `free-threaded-support`: that the library is supported and CI-verified on a
  free-threaded build of its supported interpreter, and the thread-safety
  properties callers and contributors may rely on.

### Modified Capabilities

None.

**`install-smoke-test` is deliberately left alone.** An earlier draft of this
proposal added the free-threaded leg there too, on the reasoning that wheel tags
differ between builds and that a dependency might ship no free-threaded wheel.
Both are false for this package, and the check is worth stating: `uv build
--wheel` produces `snakestream-<version>-py3-none-any.whl` — pure Python, no C
extension — and `project.dependencies` is empty, so there is no dependency whose
wheels could differ. The leg would install a byte-identical artifact a second
time. The one thing it could catch, that the package fails to import on a
free-threaded interpreter, is already caught by the `code_check` leg, which
imports it throughout a 1000-test suite.

## Impact

- `.github/workflows/check.yml` — the `code_check` matrix only, plus three
  re-introduced `if:` conditionals
- `CLAUDE.md`
- `openspec/specs/` — one new capability
- **Nothing under `src/`**

### Audit findings, recorded here because they are the change's substance

Verified against the tree at `497e435`:

- **No module-level mutable state exists in `src/snakestream`.** Checked by
  pattern over every module: no list, dict or set is bound at module scope.
- **Every `ClassVar` is an immutable declaration** — `Ordering.PRESERVE`,
  `order_sensitive: bool`, `is_parallel: bool`, `_sink_cls`. None is mutable
  shared state.
- **There are exactly two lock sites**, both `asyncio.Lock` in `execution.py`,
  guarding the shared-source pull. They are correct today because one event loop
  owns everything. **Under a forking executor with a loop per worker thread they
  become cross-thread and an `asyncio.Lock` will no longer be sufficient.** This
  is the single most important thing this audit hands forward.
- **Per-composition dispatch state does not leak.** `AsyncDispatch`'s
  `_fn`/`_is_async`/`_checked` are per-sink and a sink is built once per
  composition, which `callable_dispatch.py` already documents as a requirement
  against racing branches; the same property is what will make it safe across
  threads.
- **Coverage measures identically on both builds** — 1512 statements, 2 missed,
  99% on the free-threaded build and on the GIL build alike. An earlier
  measurement suggesting otherwise was an artifact of measuring two installed
  copies of the package, not a property of the interpreter.
