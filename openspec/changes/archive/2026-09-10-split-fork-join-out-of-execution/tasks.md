## 1. Extract `pipeline.py`

- [x] 1.1 Create `src/snakestream/pipeline.py` and move the seven sink-driving
  primitives into it verbatim — `maybe_aclosing`, `wrap_sink`, `copy_into`,
  `stream_through`, `feed_through`, `drain`, `accumulate_into` — dropping the
  leading underscore on each per CLAUDE.md's naming rule (design.md — Decision
  1). Verify `uv run pytest` is green and `git diff --stat` shows insertions
  matching deletions for this step: it is a pure move, and any net change in
  line count is an unintended edit.
- [x] 1.2 Update `execution.py` to import the seven from `snakestream.pipeline`
  and verify `uv run ty check src` passes with no unresolved-import errors.
- [x] 1.3 Update `tests/test_sequential.py:7,:40` (`_wrap_sink` from
  `snakestream.execution` -> `wrap_sink` from `snakestream.pipeline`) and the
  literal fixture tuple in `tests/test_name_visibility.py:64`. Verify
  `uv run pytest tests/test_sequential.py tests/test_name_visibility.py` is
  green — the visibility test must still find its synthetic violation, not pass
  by finding nothing.
  **Scope note:** after `wrap_sink` was moved and made bare, `test_sequential.py`
  no longer imports any underscore-prefixed name, so it could no longer serve
  as this fixture's white-box example. Retargeted the fixture at
  `test_racing_encounter_order.py` importing `_pull_round` from
  `snakestream.fork_join` instead (still underscored, still cross-module,
  post-task-2). Both files pass.

## 2. Extract `fork_join.py`

- [x] 2.1 Create `src/snakestream/fork_join.py` and move `WORKERS` plus the
  eleven fork/join definitions into it verbatim (design.md — Decision 1's
  diagram lists them). Drop the underscore on `fork_join_through` and
  `fork_join_partitioned` only; everything else stays private to the module.
  Verify `uv run pytest` is green and this step too is insertion/deletion
  balanced.
- [x] 2.2 Update `execution.py` to import `WORKERS`, `fork_join_through` and
  `fork_join_partitioned` from `snakestream.fork_join`, and confirm
  `execution.py` is now ~110 lines holding only `Executor`, `_Sequential`,
  `_ForkJoin`, `SEQUENTIAL`, `FORK_JOIN`. Verify `stream.py` needed **no**
  import change (`git diff src/snakestream/stream.py` shows only comment edits
  from task 6.2) — that invariant is the point of keeping the module's name.
- [x] 2.3 Update `tests/test_racing_encounter_order.py:22` (imports of
  `_fork_join_ordered_batches`, `_pull_round`, `_run_batch_async`) **and** the
  monkeypatch string at `:473`, `"snakestream.execution._pull_round"` ->
  `"snakestream.fork_join._pull_round"`. Verify by running the file and
  asserting the spy still records calls: the patch target is a string, so a
  stale one fails at run time and a silently no-op patch can leave the test
  passing for the wrong reason (design.md — Risks).
  **Added scope:** the same file has a second string monkeypatch pair not
  named in proposal.md's Impact — `"snakestream.execution.batch"` and
  `"snakestream.execution.asyncio.to_thread"` in
  `test_a_short_circuiting_terminal_is_charged_the_climb_not_the_ceiling` —
  which also broke at runtime (`AttributeError` on `mock.patch.__enter__`)
  since both `batch` and `asyncio.to_thread` dispatch now live in
  `fork_join.py`. Retargeted to `snakestream.fork_join.batch` and
  `snakestream.fork_join.asyncio.to_thread`; full suite green.
- [x] 2.4 Run `uv run pytest tests/test_name_visibility.py` and confirm no new
  violation: every name crossing the two new module boundaries is bare, and
  every name that stopped crossing one is underscored.

## 3. Re-home the module docstrings

- [x] 3.1 Rewrite `execution.py`'s module docstring to describe only the
  `Executor` protocol and its two values, dropping the 22 lines about
  fork/join. Verify by reading it against the file: no sentence names a
  function the module no longer contains.
- [x] 3.2 Write `pipeline.py`'s and `fork_join.py`'s module docstrings, moving
  the displaced prose (including the fork/join narrative and the `PROCESSES`
  rename history) to the module whose code it describes. Verify
  `uv run ruff check .` and `uv run ruff format --check .` pass.

## 4. Collapse the duplications

Five duplications, three helpers, one deliberate non-merge — each helper a
separate commit so the one behaviour-preserving subtlety is reviewable on its
own (design.md — Risks).

- [x] 4.1 Add `_gather_or_cancel(tasks)` and route `_run_batch_async`,
  `_run_partition_round` and `_run_round` through it (design.md — Decision 3).
  Leave `_fork_join_unordered_batches`'s differently-shaped `except` in place,
  adding a comment pointing at the helper. Verify `uv run pytest` is green,
  including the exception-propagation tests that assert the *original*
  traceback rather than a wrapper.
- [x] 4.2 Add `_rounds(source, workers)` and route `_fork_join_ordered_batches`
  and `_fork_join_partitioned` through it (design.md — Decision 4). **Verify
  the pre-first-pull cancellation guard survives**: `_fork_join_partitioned`
  must keep an explicit `head.cancellation_requested()` check *before* the
  `async for` plus a `break` at the end of the body, and must keep its
  `# pragma: no branch`. An `async for` alone pulls round one before the body
  runs and would silently drop the guarantee — no terminal reaches it today,
  which is exactly why its loss would go unnoticed.
- [x] 4.3 Add `_shared_state(chain)` and route `_fork_join_partitioned` and
  `_fork_join_batches` through it (design.md — Decision 6). Verify
  `uv run pytest tests/test_callable_dispatch.py tests/test_fork_join.py` is
  green — the state map is what keeps classification once-per-composition
  across batches.
- [x] 4.4 Confirm `_run_round` and `_run_partition_round` remain two named
  functions and were **not** merged into one parameterized by callable
  (design.md — Decision 5). Verify by reading the diff: two two-line bodies
  with distinct return types.

## 5. Verify the whole change

- [x] 5.1 Run `uv run pytest` on the GIL-enabled leg and
  `uv run --python 3.14t pytest` on the free-threaded leg; both green. The
  fork/join machinery is where the two legs diverge, so one leg is not
  evidence for the other.
  Ran as `uv run --python 3.14 pytest` (1172 passed) and
  `uv run --python 3.14t pytest` (1172 passed).
- [x] 5.2 Run `uv run pytest --cov-fail-under=98`, `uv run ruff check .`,
  `uv run ruff format --check .` and `uv run ty check src`; all pass. Check
  that the two pragma'd unreachable branches moved with their code and that
  task 4.2's explicit guard kept its `# pragma: no branch`.
  Coverage 98.64%-98.65% on both legs; `fork_join.py` at 100% lines and
  branches (its pragma'd cancellation checks and the pre-pull guard's
  `# pragma: no branch` all still exclude cleanly). Ruff, format and ty all
  pass.
- [x] 5.3 Run the existing fork/join benchmark once before and once after, on
  both legs, and record the figures in the closing `decisions.md` entry. This
  is confirmation, not a gate: nothing in this change sits on a per-element
  path (design.md — Risks), and no task above is blocked on a number. Use the
  established harness — Python 3.14.5, best of 5, interleaved rather than
  block-sequential, per `extract-racing-task-lifecycle`'s two measurement traps.
  No checked-in benchmark script exists (same as prior entries' harnesses);
  wrote an ad hoc scratch script (`Stream(vals).parallel().map(cpu_bound).collect(to_list())`
  vs `.sequential()`, 4000-iteration CPU-bound mapper, `time.perf_counter()`,
  median of 5 trials, n=200 and n=4096) and ran it against the working tree
  (after) and, via `git stash` of just this change's file set, against
  pre-split `execution.py` (before), on both `3.14` and `3.14t`. Figures agree
  within trial-to-trial noise on both legs (e.g. 3.14t, n=4096: before
  seq=580.75ms/par=312.34ms, after seq=581.12ms/par=319.91ms) — no measurable
  change, as design.md predicted for a pure module move.

## 6. Sweep the stale prose

- [x] 6.1 Correct the four spec statements citing `_wrap_sink()`:
  `openspec/specs/pipeline-composition/spec.md` :3 (Purpose), :8 and :231 (two
  SHALL statements), and `openspec/specs/stream-iterator/spec.md` :25. Scope is
  exactly the identifier `_wrap_sink()` -> `wrap_sink()` plus the module name
  where a sentence already names a location. **No SHALL is added, removed,
  reordered or otherwise reworded** — anything beyond that scope means a
  requirement really is changing and needs its own delta and its own change
  (design.md — Decision 8; this change is `skip_specs: true`). Verify with
  `git diff openspec/specs/` showing only those token substitutions, and
  `uv run pytest tests/test_roadmap.py` green so no ref went stale.
- [x] 6.2 Correct the comments naming these functions by an old underscore or
  an old module: `src/snakestream/stream.py:99` (`execution._maybe_aclosing()`)
  and `:113` (`execution._fork_join_batches()`), `src/snakestream/sink.py:218`
  (`_drain()`), `tests/test_fork_join.py:269,:312` (`_pull_round()`),
  `tests/test_close.py:298,:312` (`_maybe_aclosing()`),
  `tests/test_sink.py:146,:596` (`_copy_into()`). Verify with
  `grep -rn "_wrap_sink\|_stream_through\|_maybe_aclosing\|_copy_into\|_drain\|_feed_through\|_accumulate_into\|_fork_join_through\|execution\._" src/ tests/ openspec/specs/`
  returning nothing that names a function by a spelling the tree no longer has.
  **Note on `tests/test_fork_join.py:269,:312`:** these name `_pull_round()`
  by function name only, no module qualifier, so the underscore and spelling
  are both still correct as written (only the module changed, silently, which
  the comment never named) — left unchanged.
  **Added scope beyond proposal.md's Impact list:** the verification grep also
  caught three more stale `execution._run_element()` references naming the old
  module for a function that moved to `fork_join.py`:
  `src/snakestream/ops.py:42`, `src/snakestream/callable_dispatch.py:62`,
  `tests/test_callable_dispatch.py:265`, plus one in
  `openspec/specs/callable-dispatch/spec.md:38` (a parenthetical function
  reference, not a SHALL statement — corrected in place on the same
  no-behaviour-change grounds as decision 8, since only the identifier's
  module changed and no requirement text did). All four fixed; the same grep
  now returns nothing.

## 7. Close out

- [x] 7.1 Confirm no `README.md` Migration entry is needed and state that
  absence as a claim in the commit body: no name in this change is re-exported
  from `snakestream/__init__.py` and `stream.py`'s imports are unchanged, so
  nothing a caller can import or observe changed. Same deliberate absence
  `extract-racing-task-lifecycle` recorded.
  Confirmed `from snakestream.execution import WORKERS` still resolves (4) —
  `execution.py` imports `WORKERS` from `fork_join.py` into its own namespace,
  so the existing 0.3.5 Migration entry naming that import path stays true
  without a new entry. `git diff src/snakestream/stream.py` shows only the two
  comment edits from task 6.2, no import change.
- [x] 7.2 Archive the change (`openspec archive split-fork-join-out-of-execution`)
  and add its entry to `roadmap/decisions.md` as the new top entry, recording
  the `skip_specs`/in-place-prose decision, task 5.3's figures, and decision
  7's note that `WORKERS` moved module. No roadmap item is closed by this
  change — none exists for it — so `roadmap/README.md`'s index is unchanged;
  verify with `python tools/roadmap_index.py` producing no diff.

## Post-implementation review corrections

A peer session reviewed the diff before archiving and found two items, both
addressed here so they land in the same closing `decisions.md` entry as the
rest of the change:

- **Naming-rule regression, fixed.** `pipeline.py`'s `copy_into` was left bare
  after the move, but it has exactly one caller outside its own definitions
  (`feed_through`/`drain`, both in `pipeline.py` itself) and no cross-module
  caller — only comment mentions in `fork_join.py` and two test comments,
  which don't count under CLAUDE.md's rule. It was correctly `_copy_into` in
  `execution.py` before the split; this was a regression against the rule the
  change itself invokes, and `test_name_visibility.py` structurally cannot
  catch it (it only enforces the "no cross-module private import" half, not
  "a bare name really has no caller"). Renamed back to `_copy_into()` at its
  definition and both call sites in `pipeline.py`, plus the docstring mentions
  and the three comment references in `fork_join.py` and `tests/test_sink.py`.
  `grep -rn "copy_into" src/ tests/` now shows every hit carrying the
  underscore. Full suite re-verified (1172 passed, unchanged coverage,
  ruff/format/ty clean, both interpreter legs).
- **`accumulate_into` moved to `fork_join.py` as `_accumulate_into`, judgment
  call taken.** It was rule-compliant as a bare name in `pipeline.py` (used
  from `fork_join.py`, a different module), but it has exactly one consumer
  (`_run_partition_sync`), its semantics are fork/join-specific (a
  partitioned terminal's peer must not be finished), and its own docstring
  had to name its single caller by module to make sense — the same shape
  design.md's decision 6 already used to justify putting the state-map build
  in `fork_join.py` rather than `pipeline.py` ("it is fork/join's alone").
  Moved it next to `_run_partition_sync`, its only caller, as `_accumulate_into`;
  its docstring now points at `pipeline._copy_into()` (the sibling it's
  shaped like) instead of reaching outward to explain itself. This narrows
  `design.md`'s original decision-1 diagram, which had listed `accumulate_into`
  as one of the seven pipeline.py primitives — recorded here as the
  correction, since the diagram was proposed before this name had a second
  module competing for it. `pipeline.py` now exports six names, not seven.
  Re-verified: 1172 passed, same coverage, ruff/format/ty clean, no stale
  `accumulate_into` references remain outside `fork_join.py`.
