## 1. The partition protocol

- [x] 1.1 Add the partition protocol to `TerminalSink` in `sink.py`: the ability to report whether it partitions, to spawn a peer accumulation, and to merge a peer's container in. Verify the base declines by default, so every terminal that does not opt in is untouched (design decision 1).
- [x] 1.2 Verify no knowledge of `CollectorSink` or `ReduceSink` leaks into `execution.py` — it knows about neither today and this change must not be what changes that.
- [x] 1.3 Add the protocol's contract to `sink-protocol`'s spec as a delta, or record why it belongs in `parallel-reduction` alone.

## 2. The executor

- [x] 2.1 Override `value()` on `_ForkJoin`: where the terminal partitions, accumulate each batch into its own container inside the worker thread; otherwise fall through to today's `_drain()` path. Verify the non-partitioning path is byte-identical in behaviour to before.
- [x] 2.2 Merge partial containers by left fold in **batch order** (design decision 2). Verify with a combiner that is associative but **not commutative** — string concatenation — that the parallel result equals the sequential result rather than a permutation.
- [x] 2.3 Verify `unordered()` does **not** change merge order: the same non-commutative test with `.unordered()` queued must give the same answer. This is the plausible-looking mistake the spec calls out.
- [x] 2.4 Verify `_Sequential` produces exactly one partition and never invokes a supplied combiner.
- [x] 2.5 Verify an element lands in exactly one partition — none dropped, none twice — over a chain containing `filter` (drops) and `flat_map` (multiplies).

## 3. The two public surfaces

- [x] 3.1 Make `collect(supplier, accumulator, combiner)`'s combiner live. Verify a hand-rolled `collect(dict, accumulate, merge)` under `.parallel()` gives the sequential result, and that the combiner is actually invoked (assert on a counting merge, over a source spanning several batches).
- [x] 3.2 Add the `reduce(identity, accumulator, combiner)` overload. Verify the existing two overloads still dispatch correctly — the `UNSET` sentinel now has to distinguish three arities, which is where a dispatch bug would hide.
- [x] 3.3 Verify the three-argument `reduce()` under `.sequential()` equals the two-argument form's result for the same identity and accumulator.
- [x] 3.4 Verify `ty check src` accepts the new overload and that `tests/typing/` fixtures still behave as declared — including the two negative ones, which must still fail.

## 4. Collectors: combiners, and refusals

- [x] 4.1 Add leaf combiners: `to_list`, `to_set`, `to_collection`, `counting`, `joining`, `summing_int`/`summing_long`, `summarizing_int`/`summarizing_long`, `min_by`/`max_by`, `reducing`, and the two-argument `to_map`. Each needs a delta on its own capability spec.
- [x] 4.2 Verify `min_by`/`max_by` keep first-of-tied-wins under partitioning — a left-biased merge over contiguous partitions preserves it, and this is the case that proves combinable and `UNORDERED` are independent (design decision 4).
- [x] 4.3 Derive combiners from downstream for `grouping_by`, `partitioning_by`, `mapping`, `collecting_and_then`, by the rule `characteristics` already uses. Verify a composite over a **non**-combinable downstream declares none and still gives the sequential result.
- [x] 4.4 Leave `summing_double`, `summarizing_double` and **all three** `averaging_*` without a combiner, and state the reason in each capability's spec: they accumulate into `float` (`_AvgBox.total`, shared `_averaging()`), and float addition is not associative. Verify `averaging_int` is excluded too despite its integral element type — that is the one a future reader will try to "fix".
- [x] 4.5 Leave `to_map(key_mapper, value_mapper, merge_function)` without a combiner and state why (design decision 5). Verify the two-argument form partitions and the three-argument form does not.
- [x] 4.6 For **every** collector gaining a combiner, add a test asserting the `.parallel()` result equals the `.sequential()` result over a source spanning **several batches**. A source small enough to be one partition never merges and would pass regardless — that is the trap (design: Risks).

## 5. The inverse spec sweep (the gap that let the last regression through)

- [x] 5.1 Before implementation is called done, sweep `openspec/specs/` for requirements the **new partitioned path** might violate — the inverse of the last change's audit question, which only asked whether deleted tests mapped to surviving requirements (design: Risks). Start with `callable-dispatch`, `collector-protocol`, `terminal-sinks`, `stream-execution-model`, `comparator-contract`, and the per-collector capabilities.
- [x] 5.2 For each spec found, record verdict: still true / needs a delta / genuinely violated. Write the table into the change directory as a reviewable artifact, as `test-audit.md` was.
- [x] 5.3 Specifically verify `callable-dispatch`'s "classified once per composition" still holds on the partitioned path — a per-batch terminal sink must not reintroduce per-element classification through the collector's own callables.
- [x] 5.4 Specifically verify `comparator-contract`'s tie-breaking and stability requirements hold for `min_by`/`max_by` under partitioning.

## 6. Prose

- [x] 6.1 README: the `collect(supplier, accumulator, combiner)` row stops saying the combiner is "not invoked"; the three-argument `reduce()` row stops saying "not yet implemented". Verify neither row still describes the blocker as current.
- [x] 6.2 README Migration entries: the combiner becoming live (silent — a caller passing a non-associative combiner gets a different answer under `.parallel()` where before the parameter was ignored entirely; this is the **one place** an existing call site's result can change, and it must be named plainly), and the new `reduce()` overload (additive).
- [x] 6.3 `CLAUDE.md`: the Collectors section states the combiner is never invoked. Rewrite it, and describe the partitioning path in the execution section.
- [x] 6.4 `roadmap.md`: resolve the "Make combiners mean something" **Later** item — the last of the three the free-threading sequence was for. Record finding (b) as *spent* rather than deleting it, so the reasoning stays findable.

## 7. Measure

- [x] 7.1 Re-run the collector benchmark from `proposal.md` — `grouping_by(slow_key)` and `to_map(slow_key, cheap)` — and verify they now scale rather than sitting at 0.98x. These are the numbers this change exists to move.
- [x] 7.2 Measure per collector whether the combiner pays. A collector where merging measurably costs more than the accumulation it parallelised should have its combiner **removed**, not kept for symmetry (design: Risks). Record the figures.
- [x] 7.3 Verify no regression on the cheap-mapper case against the pre-change tree, using the same harness `fork-join-executor-and-spliterator`'s `benchmark-findings.md` established.
- [x] 7.4 If the merge dominates for cheap accumulators, record the numbers against design.md's Open Question — one partition per worker rather than per batch — without acting on it in this change.

## 8. Validate

- [x] 8.1 Run `ruff check .`, `ruff format --check .`, `pytest`, `ty check src`, `pytest --cov-fail-under=98` on **both** CI legs.
- [x] 8.2 Run `openspec validate make-combiners-live`; verify valid.
- [x] 8.3 Verify every existing test still passes unmodified except where a delta explains the change — this change moves where work runs, not what it produces.
