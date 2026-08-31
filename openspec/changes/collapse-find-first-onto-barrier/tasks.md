## 0. Preconditions

- [ ] 0.1 Confirm `collapse-for-each-ordered-onto-barrier` is archived and its deltas are in the main specs. This change removes requirements by the names that change introduces; applied first, its removals silently no-op and `openspec validate` will not catch it.
- [ ] 0.2 Confirm `find_first()` is the only remaining caller of `_evaluate()`'s `executor` parameter and the only remaining user of `terminal-sinks`' ordered-drive requirement.

## 1. The demand type

- [ ] 1.1 Add `OrderDemand(Enum)` to `src/snakestream/execution.py` with `NONE`, `IF_ORDERED` and `ALWAYS`, and a docstring pairing it with `sink.Ordering`: `Ordering` says what an op does *to* the encounter-order characteristic, `OrderDemand` what a terminal asks *of* it. Record that Java has no counterpart to name it after, because its terminals answer by choosing a task class.
- [ ] 1.2 Widen `Executor.elements()` and `Executor.value()` to take `demand: OrderDemand`, renaming the parameter from `observes_order` on both. Keep `Executor`'s existing rationale for the declaration living on the protocol rather than on the terminal sink — only the type changes.
- [ ] 1.3 Update `Sequential.elements()`/`value()` signatures; the accepted-and-ignored comment stands as written.
- [ ] 1.4 Widen `race_through()`'s and `_run_ordered_tail()`'s `observes_order` parameter to `demand: OrderDemand`, including the recursive `race_through()` call that carries it across a split.
- [ ] 1.5 Rewrite `_split_point()`'s third clause as `demand is ALWAYS or (demand is IF_ORDERED and is_ordered(chain, initial=ordered_in))`, and extend its docstring's three-clause walkthrough to state the op/terminal symmetry the two-by-two table in design.md draws.

## 2. Call sites

- [ ] 2.1 In `stream.py`, convert every `_evaluate()` call site from a bool to an `OrderDemand`: `NONE` for `count()`, `for_each()`, `find_any()`, `max()`/`min()` via `_min_max()`, and the `*_match` family; `IF_ORDERED` for `reduce()`, the three-argument `collect()`, and `for_each_ordered()`.
- [ ] 2.2 Convert `iterator()`'s `self._executor.elements(..., True)` to `IF_ORDERED`.
- [ ] 2.3 Convert `collect(collector)`'s characteristic read to `NONE if Characteristics.UNORDERED in collector.characteristics else IF_ORDERED`. A collector can never yield `ALWAYS`; keep the existing comment's reasoning.
- [ ] 2.4 Replace `find_first()`'s body with `return await self._evaluate(_FindSink(), OrderDemand.ALWAYS)` and rewrite its comment: the Java citation now lands on `FindTask` doing its leftmost scan *across branches*, which is what makes the demand-not-executor framing the parity-correct one.
- [ ] 2.5 Remove `_evaluate()`'s `executor` parameter and the `(executor or self._executor)` expression, and rewrite the docstring paragraph that cites `find_first()`'s executor as the sibling posture — the two axes are now one axis plus a three-valued declaration.
- [ ] 2.6 Verify `SEQUENTIAL` is still imported and used by `Stream.concat()`, and that `Stream._is_ordered()` still has `concat()` as a caller. Neither is removed by this change.
- [ ] 2.7 Annotate every widened parameter explicitly as `OrderDemand` so `ty` catches a missed call site; run `uv run ty check src` before proceeding to remove the `executor` parameter, so the two mechanical edits fail independently.

## 3. Tests

- [ ] 3.1 `tests/test_execution_model.py`: rewrite `test_find_first_on_an_ordered_parallel_stream_ignores_the_executor` and `test_find_first_holds_when_the_op_is_declared_before_parallel` — the returned-element assertions stand, the "drives under SEQUENTIAL" comments do not.
- [ ] 3.2 `tests/test_execution_model.py`: fix `test_find_first_on_an_unordered_stream_does_not_force_sequential`. **Its assertion is `it in [1, 2, 3, 4]` and its comment says "behaves as find_any(), so any element is admissible"** — already contradicting `stream-find-first` and `tests/test_terminal_sinks.py:265`, which asserts the exact element. Tighten it to `== 1`.
- [ ] 3.3 `tests/test_terminal_sinks.py:265`: update the comment "it drives SEQUENTIAL either way" while keeping the assertion.
- [ ] 3.4 Add a test that a parallel `find_first()` races its chain: `.parallel().filter(p).find_first()` over a source whose first several elements fail an expensive predicate returns the correct element and completes substantially faster than `.sequential()`.
- [ ] 3.5 Add a test that `.parallel().map(f).find_first()` returns the correct element in wall-clock time comparable to sequential — the no-regression half of the measurement.
- [ ] 3.6 Add speculation-bound tests: a parallel `find_first()` invokes the mapper more than once when the head element is slow, and never more than `_READ_AHEAD` times. **Assert the invariants (`> 1`, `<= _READ_AHEAD`), never the measured `PROCESSES` figure** — design.md's flakiness note.
- [ ] 3.7 Add the sequential companion asserting exactly one invocation, which is where `== 1` is safe.
- [ ] 3.8 Add a test that `ALWAYS` survives a split: `.parallel().sorted(c).unordered().map(f).find_first()` returns the leftmost element of the sorted order.
- [ ] 3.9 Add a test that a parallel `find_first()` over a slow, effectively unbounded source terminates and leaves no pending tasks — **no short-circuiting terminal has ever driven `_release_in_order()`'s cancellation path**, per design.md's first risk.
- [ ] 3.10 Add a test that `.parallel().unordered().limit(n).find_first()` no longer forces the whole pipeline deterministic, asserting only what the specs now promise.
- [ ] 3.11 Measure `.parallel().find_first()` on an empty chain against its sequential counterpart. If the degenerate-case regression is material, add an empty-chain fast path in `race_through()`; if not, record the figure in a comment and move on.

## 4. Specs and docs

- [ ] 4.1 Run `openspec sync` (or apply the deltas by hand) for `stream-find-first`, `stream-execution-model`, `racing-encounter-order` and `terminal-sinks`.
- [ ] 4.2 `README.md`: update the `find_first()` parity-table row (line 181) — the guarantee stands, "driving under the sequential executor" does not.
- [ ] 4.3 `README.md`: migration entry for `find_first()` no longer overriding `unordered()`. Frame it as the withdrawal of a suppression — an order-sensitive op on an unordered chain already answered arbitrarily under every other terminal — and name `.sequential()` as the restoration.
- [ ] 4.4 `README.md`: migration entry for repeated invocation of a side-effecting chain callable, with both bounds and the `.sequential()` escape hatch.
- [ ] 4.5 `README.md`: check the 0.3.5 migration entry at line 291, which says `find_first()` works "by driving under the sequential executor regardless of the stream's mode". Historical entries are a log and should not be rewritten; add the correction in the new entry instead, pointing back at it.
- [ ] 4.6 `CLAUDE.md` line 61: rewrite the "A terminal that needs encounter order regardless of the stream's mode names `SEQUENTIAL`" sentence — no terminal does now. Describe the three-valued declaration and keep the `_is_ordered()`-is-not-public paragraph, whose reasoning is unchanged.
- [ ] 4.7 `CLAUDE.md` line ~111: remove the "`find_first()` and `for_each_ordered()` still name `SEQUENTIAL` at their own call sites" sentence and fold `find_first()` into the declaration list as the sole `ALWAYS`.
- [ ] 4.8 `CLAUDE.md`: update the ordering-barrier section's `_split_point()` walkthrough to three clauses with the op/terminal symmetry.
- [ ] 4.9 `roadmap.md`: archive item 2 into Done with the measured figures and the two corrections it produced — `_is_ordered()` survives, and the speculation bound has two regimes rather than the flat "≤15 maps" the item claimed.
- [ ] 4.10 `roadmap.md` item 3: note that `_READ_AHEAD` now also bounds speculative work in a short-circuiting terminal — the first thing it bounds that a caller can observe other than memory and latency, which strengthens the export case and complicates the rename.

## 5. Validation

- [ ] 5.1 `uv run pytest` — full suite green.
- [ ] 5.2 `uv run ruff check .` and `uv run ruff format --check .`
- [ ] 5.3 `uv run ty check src`
- [ ] 5.4 `uv run pytest --cov-fail-under=98`
- [ ] 5.5 Re-run `bench_find_first.py` and `bench_speculation.py` against the implementation and confirm the figures in `proposal.md` hold — they were measured through `iterator()` as a stand-in, so this is the first check that the real `find_first()` matches.
- [ ] 5.6 Run the timing-sensitive tests repeatedly to confirm they are not flaky.

## 6. Archive

- [ ] 6.1 `openspec archive collapse-find-first-onto-barrier`, then sweep for a stale `## Purpose` — `stream-find-first`'s opens by saying it "names the sequential executor for its own drive", which this change removes, and `terminal-sinks`' summary mentions the ordered drive that no longer exists.
