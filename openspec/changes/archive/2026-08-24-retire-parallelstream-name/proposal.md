## Why

`replace-parallel-stream-with-executor` (archived 2026-08-21) deleted the
`ParallelStream` class and replaced it with execution mode as a value
(`SEQUENTIAL`/`RACING`), but the name it retired did not fully disappear.
Three places the change did not reach still describe behaviour in terms of a
class that no longer exists: two requirements in `openspec/specs/` whose text
was never updated (one from a delta that was declared in that change's
proposal but never written, one from a scan that was truncated before it
found two more requirements in `pipeline-composition`), ten spec `## Purpose`
sections (which a delta cannot touch — OpenSpec ignores `MODIFIED` blocks
against Purpose — so they were left stale), and five docstrings plus four
scenario titles kept deliberately because a `MODIFIED` scenario block may not
drop a name the main spec still uses.

None of this is a behaviour gap — every described behaviour is still correct
and still covered by the 535-test suite. It is readability debt of the
misleading kind: a reader grepping for `ParallelStream` today finds specs and
docstrings that promise a class the codebase no longer has. Doing it as one
pass retires the name in a single commit instead of it leaking across
several unrelated ones.

## What Changes

- Write the delta spec for `stream-foreach-ordered` that
  `replace-parallel-stream-with-executor`'s proposal declared as a Modified
  Capability but never delivered: its "for_each_ordered() preserves encounter
  order on ParallelStream" requirement, and the scenario titled `ParallelStream
  yields ordered results via for_each_ordered`, are rewritten in terms of
  `.parallel()` / `RACING` execution instead of a `ParallelStream` instance.
- Write the delta spec for `pipeline-composition`'s two requirements missed by
  that change's truncated scan — *Parallel `skip()` remains globally correct
  across branches* and *Parallel branches serialize pulls from the shared
  upstream source* — rewording their `ParallelStream` references (class,
  `._parallel()`, `._compose()`) to the current `RACING` executor and
  `race_through()`/`_parallel()` primitives in `execution.py`.
- Directly edit (outside any delta, since deltas cannot touch Purpose) the
  ten `## Purpose` sections in `openspec/specs/` that still name
  `ParallelStream`: `pipeline-composition`, `stream-close-handling`,
  `terminal-sinks`, `stream-find-first`, `stream-foreach-ordered`,
  `generic-stream-typing`, `stream-ordering`, `mutable-reduction-collect`,
  `pipeline-immutability`, `stream-iterator`.
- Directly edit the five docstrings in `src/snakestream/sink.py` (4) and
  `src/snakestream/callable_dispatch.py` (1) that still say `ParallelStream`.
- Rename the four scenario titles that still carry the old name where the
  main spec text (not a delta) controls them: `Works on ParallelStream`,
  `iterator() on a ParallelStream`, `ParallelStream inherits the element
  type`, `ParallelStream yields ordered results via for_each_ordered`.

No public API changes, no behaviour changes. Not marked **BREAKING**.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `stream-foreach-ordered`: the "for_each_ordered() preserves encounter order
  on ParallelStream" requirement and its scenario are reworded to describe
  `.parallel()`/`RACING` execution instead of a `ParallelStream` instance —
  same guarantee, current vocabulary.
- `pipeline-composition`: the "Parallel `skip()` remains globally correct
  across branches" and "Parallel branches serialize pulls from the shared
  upstream source" requirements are reworded from `ParallelStream`/
  `._parallel()`/`._compose()` to the `RACING` executor and
  `execution.py`'s `race_through()` primitive — same guarantees, current
  vocabulary.

## Impact

- `openspec/specs/stream-foreach-ordered/spec.md`,
  `openspec/specs/pipeline-composition/spec.md`: requirement text updated via
  delta specs in this change.
- `openspec/specs/*/spec.md` (8 further files listed above): `## Purpose`
  sections edited directly, no delta.
- `src/snakestream/sink.py`, `src/snakestream/callable_dispatch.py`:
  docstring wording only, no code-path change.
- No `src/` behaviour change, no test assertions change (test names may be
  grepped for `ParallelStream` but this change does not require renaming test
  identifiers, which are not part of the public API).
- README: no parity-table or migration-log entry needed — no public API
  changed.
