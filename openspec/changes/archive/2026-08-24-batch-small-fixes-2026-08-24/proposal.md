## Why

The 2026-08-24 legibility batch on the execution path is otherwise finished (six of seven items landed; see `roadmap.md`'s **Now**). The one item left is three unrelated one-or-two-line inconsistencies noticed during that same read — each too small for its own commit, but each either misleading a future reader or silently disagreeing with the README.

## What Changes

- `unordered()` (`stream.py:151`) and `on_close()` (`stream.py:158`) mutate `self` and return it, unlike all eight intermediate operations, which derive-and-consume. This is deliberate and already required by the `stream-ordering` spec and `pipeline-immutability` spec, but nothing at the call site says so — add a one-line docstring note on each pointing at the requirement it satisfies.
- Export `PROCESSES` from `snakestream/__init__.py` so `from snakestream import PROCESSES` works. Purely additive, not breaking: today `stream.py` re-exports it from `snakestream.execution` but the top-level package never re-exports it, even though README documents `.parallel()`/`PROCESSES` as a stable public pair. This closes that gap by making the documented behavior real rather than rewording the README to match the narrower reality.
- Remove the four `# pylint: disable=missing-*-docstring` / `# pylint: disable=invalid-name` pragmas at the top of `collector.py` (`collector.py:1-4`). Confirmed dead: this project lints with `ruff`, not `pylint` — no `pylint` config or invocation exists anywhere in the repo — and `collector.py` is already fully docstringed.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `stream-execution-model`: `PROCESSES` becomes part of the package's public export surface (`from snakestream import PROCESSES`), not just `snakestream.execution.PROCESSES` / the `stream.py` re-export.

## Impact

- `src/snakestream/stream.py`: two docstring additions (`unordered()`, `on_close()`), no behavior change.
- `src/snakestream/__init__.py`: one new export line for `PROCESSES`.
- `src/snakestream/collector.py`: delete four pragma comment lines.
- `README.md`: no wording change needed for `PROCESSES` (it already describes the intended public pair; this change makes the import path match).
- No test file requires an edit for the docstring or pragma parts; a new import-surface test covers the `PROCESSES` export.
