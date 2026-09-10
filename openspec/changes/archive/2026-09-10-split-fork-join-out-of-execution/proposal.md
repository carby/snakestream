## Why

`execution.py` is 600 lines and 15 top-level definitions, and 11 of those
definitions — 332 lines, 55% of the file — are one concern's private machinery:
fork/join batch dispatch. The module docstring tells on it, spending 22 of its
28 lines explaining fork/join before reaching the thing the module is named
for. `stream.py`, the only consumer, touches exactly three names from all of
it: `Executor`, `SEQUENTIAL`, `FORK_JOIN`.

That placement has a cost beyond size. Duplication inside the fork/join half is
spread across 330 lines and reads as unrelated at that distance, and two of its
own comments already name it as shared —
`# same ramp as _fork_join_ordered_batches() - see its comment for the rule;
the 8 is one retunable constant shared by all three sites` appears twice, which
is a function signature written as a comment. That is the same tell
`extract-racing-task-lifecycle` was filed on (`decisions.md`, 2026-09-02):
*"Both docstrings already admitted it in prose ... which is a function
signature written as a comment."*

Splitting is the house pattern for exactly this — `collectors.py` out of
`collector.py`, `comparator.py` out of `sort.py`, `ordering.py` out of
`sink.py`/`execution.py`, `unseeded.py` out of `sink.py` are all shipped
entries in `decisions.md`. And this refactor is cleanly outside the one
criterion that has killed four prior cleanups here: it moves where code
*lives*, adding no Python-level frame to any per-element path, and the code it
does de-duplicate runs once per round — once per ~4 OS-thread dispatches — not
once per element.

Not filed as a roadmap item; found by exploration on 2026-09-10 against an
empty **Now** and **Next** queue.

## What Changes

- **Add `pipeline.py`** (~130 lines), a new module holding the sink-driving
  primitives and only those: `maybe_aclosing`, `wrap_sink`, `copy_into`,
  `stream_through`, `feed_through`, `drain`, `accumulate_into`. Named for
  Java's `AbstractPipeline`, whose `wrapSink()` and `copyInto()` are the two
  functions that head the file and which both docstrings already cite by name.
- **Add `fork_join.py`** (~300 lines), holding the parallel batch machinery:
  `WORKERS`, the batch and partition runners, the round loops, and the
  split/barrier recursion. It exports `fork_join_through()` and
  `fork_join_partitioned()`; everything else stays private to it.
- **`execution.py` keeps its name and shrinks to ~110 lines**: the `Executor`
  ABC, `_Sequential`, `_ForkJoin`, `SEQUENTIAL`, `FORK_JOIN`. What `stream.py`
  actually imports, and nothing else. Its module docstring loses the 22 lines
  about fork/join, which move with the code they describe.
- **Collapse five duplications** now visible within one file (each detailed in
  `design.md`; every one of them runs per round or per composition, never per
  element):
  - `_run_round()` and `_run_partition_round()` are the same function apart
    from which callable is handed to `asyncio.to_thread`.
  - The cancel-siblings-and-re-raise idiom appears 4x, verbatim in three of
    them (`_run_batch_async`, `_run_partition_round`, `_run_round`) and in the
    same shape over `in_flight` in `_fork_join_unordered_batches`.
  - The geometric ramp (`size = min(size * 8, BATCH_SIZE)`) is written 3x, with
    two of the three carrying a comment pointing at the third.
  - The whole round loop — seed, pull, dispatch, consume, stop-on-short-round,
    ramp — is written twice (`_fork_join_partitioned`,
    `_fork_join_ordered_batches`).
  - The state-map build loop is written twice (`_fork_join_partitioned`,
    `_fork_join_batches`).
- **Rename by the naming rule, not by choice.** Any split makes `_wrap_sink`,
  `_stream_through`, `_maybe_aclosing`, `_drain`, `_feed_through`,
  `_copy_into`, `_accumulate_into` and `_fork_join_through` cross a module
  boundary, so CLAUDE.md's rule ("underscored **iff** no other module uses it")
  drops their underscores. This is mechanical, and
  `tests/test_name_visibility.py` enforces half of it.
- **BREAKING**: none for callers. No name here is re-exported from
  `snakestream/__init__.py`, and no observable behaviour changes. Two test
  files import these names white-box and must be updated (see Impact); per
  `decisions.md`'s own precedent that is a diff shape to expect from a move,
  not a violation.

## Capabilities

### New Capabilities

None — this changes module placement and internal names, not observable
behaviour.

### Modified Capabilities

None. **Settled 2026-09-10: `skip_specs: true`.** Three requirement statements
cite `_wrap_sink()` by its underscored name and the rename below makes that
text stale:

- `pipeline-composition` — spec.md:3 (Purpose), :8 and :231 (two SHALL
  statements), each naming "the `_wrap_sink()` helper it uses".
- `stream-iterator` — spec.md:25, "linking the chain onto one sink via
  `_wrap_sink()`".

No requirement's *substance* changes; only the spelling and home of an internal
helper it happens to name. That is an implementation detail, matching
`extract-unseeded-fold-module`'s rule ("specs describe behaviour, so if
behaviour does not change, no spec should change either"), so this change
declares no delta. The stale identifiers are corrected **in place** as task
6.1, not through a MODIFIED-Requirements block that would restate four
requirements verbatim but for one token. See `design.md` — Decision 8.

## Impact

- `src/snakestream/execution.py` — loses 449 of 600 lines and 12 of 15
  definitions; keeps its name, its `Executor` protocol and its two values.
  Module docstring rewritten to describe only what remains.
- `src/snakestream/pipeline.py` — new. Imports `sink.py`, `type.py`; imported
  by `fork_join.py` and `execution.py`.
- `src/snakestream/fork_join.py` — new. Imports `pipeline.py`, `ordering.py`,
  `sink.py`, `spliterator.py`, `type.py`; imported by `execution.py` only.
- `src/snakestream/stream.py` — no import change (`Executor`, `SEQUENTIAL`,
  `FORK_JOIN` all stay in `execution.py`). Two comments name
  `execution._maybe_aclosing()` (:99) and `execution._fork_join_batches()`
  (:113) and need their module and underscore corrected.
- `tests/test_sequential.py` — imports `_wrap_sink` from `snakestream.execution`
  (:7, :40); becomes `wrap_sink` from `snakestream.pipeline`.
- `tests/test_racing_encounter_order.py` — imports `_fork_join_ordered_batches`,
  `_pull_round`, `_run_batch_async` from `snakestream.execution` (:22) and
  monkeypatches the string `"snakestream.execution._pull_round"` (:473). Both
  move to `snakestream.fork_join`. The patch target is a string, so it fails at
  runtime rather than at import — it must be found by running the suite, not by
  grepping imports.
- `tests/test_name_visibility.py` — asserts on the literal tuple
  `("tests/test_sequential.py", "snakestream.execution", "_wrap_sink")` (:64)
  as its own fixture; changes with `test_sequential.py`.
- `tests/test_fork_join.py`, `tests/test_close.py`, `tests/test_sink.py`,
  `src/snakestream/sink.py` — comments only, naming `_pull_round`, `_drain`,
  `_copy_into`, `_maybe_aclosing`. No code change; the underscores are now
  wrong in prose.
- `roadmap/` — no item is closed by this change; none exists for it. Nothing to
  move to `decisions.md` until it ships.
- `README.md` — no Migration entry. Nothing a caller can import or observe
  changes, which is the same claim `extract-racing-task-lifecycle` made and
  recorded as a deliberate absence.
