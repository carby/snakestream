## 1. Implementation

- [x] 1.1 In `src/snakestream/stream.py`, replace `for_each_ordered()`'s body with `return await self._evaluate(_ForEachSink(consumer), True)` — deleting the `executor = SEQUENTIAL if self._is_ordered() else None` line, the third argument, and the two comment lines explaining the `True`-on-both-branches reasoning.
- [x] 1.2 Rewrite `for_each_ordered()`'s docstring: the guarantee is now the delivery barrier, released on an unordered pipeline by `_split_point()` rather than by the terminal choosing an executor. Cite that `ForEachOrderedTask` is itself a fork-join task, so Java's ordered path stays parallel — the point the old citation stopped one step short of.
- [x] 1.3 Confirm `SEQUENTIAL` and `Stream._is_ordered()` are both still referenced by `Stream.concat()` (`stream.py:401-402`) and leave both in place. Do not remove the `SEQUENTIAL` import.
- [x] 1.4 Confirm `_evaluate()`'s `executor` parameter still has one caller (`find_first()`) and leave it in place — it is removed by `collapse-find-first-onto-barrier`.

## 2. Tests

- [x] 2.1 `tests/test_execution_model.py`: rename `test_for_each_ordered_ignores_the_streams_executor` and rewrite it to assert the consumer sees encounter order *and* that the chain ran under the racing executor, replacing the old "ignores the executor" premise.
- [x] 2.2 Add a test that an ordered parallel `for_each_ordered()` does not serialize the chain: have the mapper record entry/exit timestamps and assert at least two intervals overlap. Assert on overlap, not wall clock — per design.md's flakiness note.
- [x] 2.3 Add a wall-clock companion asserting the ordered parallel run is substantially faster than the same pipeline under `.sequential()`, with a loose threshold; drop it if it proves unstable in CI.
- [x] 2.4 Add a test that an operation upstream of `for_each_ordered()` carries no ordering guarantee: `peek()` records into a list, the consumer records into another, and the consumer's list is in encounter order while the `peek` list is only asserted to be a permutation.
- [x] 2.5 Add a test that moving the same side effect into the consumer restores ordering, pinning the guarantee's boundary.
- [x] 2.6 `tests/test_for_each_ordered.py`: audit for any test whose premise is single-flight execution (the comment at line 94 flags one such assumption) and update or remove it.
- [x] 2.7 Verify the unordered-pipeline tests still pass unchanged — that path is the `None`-executor branch today and the no-split branch after, and its behaviour is identical.

## 3. Specs and docs

- [x] 3.1 Run `openspec sync` (or apply the deltas by hand) for `stream-foreach-ordered`, `stream-execution-model`, `racing-encounter-order` and `terminal-sinks`.
- [x] 3.2 `README.md`: update the `for_each_ordered()` parity-table row (line 187) — the unordered case no longer contrasts with "forcing sequential execution", since neither case does.
- [x] 3.3 `README.md`: add the migration-log entry for the upstream-side-effect ordering change. State that the consumer's ordering is unchanged, that an op upstream of it now runs concurrently and out of order, that Java promises order for the action only, and that `.sequential()` restores the old behaviour.
- [x] 3.4 `CLAUDE.md` line 61: remove `for_each_ordered()` from the list of terminals naming `SEQUENTIAL` at their own call site. **Also correct the claim that `for_each_ordered()` is `_is_ordered()`'s sole caller** — `Stream.concat()` is the other, and this sentence is where the roadmap's error came from.
- [x] 3.5 `CLAUDE.md` line ~111: move `for_each_ordered()` out of the "still name `SEQUENTIAL` at their own call sites" sentence and into the list of terminals declaring `True`.
- [x] 3.6 `roadmap.md`: mark item 2's `for_each_ordered()` half landed, leaving the `find_first()` half open, and correct the "what disappears" list — `_is_ordered()` and the `SEQUENTIAL` name in `stream.py` both survive.

## 4. Validation

- [x] 4.1 `uv run pytest` — full suite green.
- [x] 4.2 `uv run ruff check .` and `uv run ruff format --check .`
- [x] 4.3 `uv run ty check src`
- [x] 4.4 `uv run pytest --cov-fail-under=98`
- [x] 4.5 Run the new concurrency tests repeatedly (e.g. `-n 20` or a loop) to confirm they are not flaky before committing.

## 5. Archive

- [x] 5.1 `openspec archive collapse-for-each-ordered-onto-barrier`, then sweep for a stale `## Purpose` in each touched main spec — `stream-foreach-ordered`'s and `terminal-sinks`' both describe the mechanism this change replaces.
- [x] 5.2 Confirm `collapse-find-first-onto-barrier` still validates against the updated main specs, since its deltas target the requirement names this change introduces.
