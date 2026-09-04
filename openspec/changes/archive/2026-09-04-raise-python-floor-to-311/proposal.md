## Why

The support floor is Python 3.10, and nothing needs it to be. This is the first
of four sequenced floor raises taking the library to 3.14-only, and the
destination is not tidiness: **free-threading (PEP 779, officially supported as
of 3.14)** is the substrate a contiguous-splitting `spliterator()` needs, and
that is what would let the racing executor be replaced rather than merely
supplemented. Free-threading keeps real object sharing — closures, lambdas and
async generators cross a thread boundary unchanged — which is exactly what
`roadmap.md`'s real-parallelism entry records as the unsolved blocker for a
`ProcessPoolExecutor`-backed implementation, and what `concurrent.interpreters`
(PEP 734) does *not* solve, since its queues move only picklable objects. The
floor cannot be raised to 3.14 in one step without an unreviewable diff, so it
is raised one minor version at a time, each step taking the lint family that
version unlocks.

Usage is near zero, which is what makes a four-step drop of four interpreter
versions a cheap decision rather than an expensive one.

This step drops 3.10. Its payoff in code is small and exact: one
`sys.version_info` fork disappears, and `Stream.close()`'s note-attaching
behaviour becomes unconditional rather than interpreter-dependent.

## What Changes

- **BREAKING**: `requires-python` moves from `>=3.10` to `>=3.11`. Installing on
  Python 3.10 now fails at resolution rather than silently working.
- **BREAKING** (behaviour, on 3.10 only): `Stream.close()` no longer has a
  no-notes path. On 3.10 it previously raised the first exception unmodified;
  3.10 is no longer supported, so the conditional is deleted and `add_note()` is
  called unconditionally. Observable behaviour on **every supported
  interpreter** is unchanged.
- The 3.10 leg is removed from both CI jobs (`code_check` and
  `install_smoke_test`); the matrix becomes 3.11–3.14.
- `ruff`'s `target-version` moves to `py311`. Two findings follow from it, both
  in `close()` and both deletions:
  - `UP036` (outdated-version-block) on the `sys.version_info` fork above.
  - `RUF100` (unused `noqa`) on the `# noqa: PERF203` two lines below it.
    `PERF203` objects to `try`/`except` inside a loop, and ruff stops raising it
    at all on 3.11+, where zero-cost exceptions removed the cost it was warning
    about. The suppression and the comment justifying it both go; the sentence
    stating why the `try` is inside the loop — `close()`'s every-handler
    contract — is kept, reworded to stand on its own rather than as a rebuttal
    to a rule that no longer fires.
- Docs and specs stating the matrix are corrected: `CLAUDE.md`, the
  `install-smoke-test` spec, and `roadmap.md`'s note that the
  `ExceptionGroup` decision's 3.10 objection had an expiry date — it has now
  expired, and the decision is unaffected because it never rested on it.
- A README Migration entry records the dropped interpreter.
- No use is made of PEP 646 (variadic generics) or PEP 681
  (`dataclass_transform`), the other two typing PEPs 3.11 unlocks. Both were
  checked against the code and declined; see `design.md`, decision 6.

## Capabilities

### New Capabilities

None. No new behaviour is introduced.

### Modified Capabilities

- `stream-close-handling`: the `close()` requirement stops being conditional on
  interpreter note support. The "on interpreters without note support (Python
  3.10)" sentence and its matching scenario are removed; note attachment becomes
  unconditional. The `ExceptionGroup` prohibition is retained verbatim except
  for its closing clause, which referenced the 3.10 floor as something the
  decision was *not* deferred pending — that clause loses its referent.
- `install-smoke-test`: the supported matrix stated in the Purpose, the
  requirement and one scenario changes from 3.10–3.14 to 3.11–3.14.

## Impact

- `pyproject.toml` — `requires-python`, `[tool.ruff] target-version`
- `.github/workflows/check.yml` — both matrices
- `src/snakestream/stream.py` — `close()`: the version fork, the `PERF203`
  suppression and its comment, and the `import sys` the fork was the only user of
- `tests/test_close.py` — any test exercising the no-note path
- `CLAUDE.md`, `README.md`, `roadmap.md`
- `openspec/specs/stream-close-handling/spec.md`,
  `openspec/specs/install-smoke-test/spec.md`
- No change to `src/` behaviour on any supported interpreter; no public API
  surface added or removed.
