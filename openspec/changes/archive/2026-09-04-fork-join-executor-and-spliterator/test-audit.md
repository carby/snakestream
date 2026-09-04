# Test audit: racing → fork/join

Section 3's gate (tasks 3.1–3.6). One row per test in the four files design.md
names plus the scattered references it names, classified against one rule:
**does it assert a requirement that survives in `openspec/specs/`?**

Verdicts:
- **guarantee / survives** — asserts an observable contract that still holds
  under fork/join. Left as-is, or mechanically updated (a name reference) if
  it names the old mechanism directly.
- **mechanism / delete** — asserts something about *how* racing worked
  internally (the delivery barrier, branch-local behaviour, a window bound)
  that has no fork/join counterpart because the thing it tested no longer
  exists.
- **narrowed / rewrite** — asserts a guarantee that decision 9 (design.md)
  narrows: `unordered()` no longer relaxes delivery order. Needs a new
  assertion reflecting the narrowed contract, not a deletion.

Found during this audit, not before it: the `aiter(source)` bug (a bare
`AsyncIterable` source broke under any non-empty chain — fixed in
`_fork_join_batches()`, regression test added to `test_fork_join.py`). Several
`test_execution_model.py` scenarios below use an **empty** chain and so never
actually exercised the code path that bug was in; noted per-row.

## tests/test_execution_model.py (27 tests) — DONE

| Test | Verdict | Requirement |
|---|---|---|
| test_a_sequentially_built_stream_reports_sequential | guarantee/survives | stream-execution-model: "A sequentially-built stream reports sequential" |
| test_a_parallel_stream_reports_parallel | guarantee/survives | stream-execution-model: "A parallel stream reports parallel" |
| test_intermediate_operations_carry_the_executor_forward | guarantee/survives | stream-execution-model: "Intermediate operations carry the executor forward" |
| test_a_user_subclass_survives_a_mode_switch | guarantee/survives | stream-execution-model: "A user subclass survives a mode switch" |
| test_a_subclass_constructor_runs_once_per_pipeline | guarantee/survives | derive-without-reinit (archived); incidental `.parallel()` use |
| test_a_resource_acquired_in_the_constructor_is_acquired_once | guarantee/survives | derive-without-reinit (archived); no `.parallel()` at all |
| test_a_mode_switch_does_not_compose_the_queued_chain | guarantee/survives | pipeline-immutability; no `.parallel()` |
| test_a_mode_switch_returns_a_distinct_object_and_consumes_the_receiver | guarantee/survives | pipeline-immutability |
| test_a_stateful_op_declared_before_parallel_stays_globally_correct | guarantee/survives | pipeline-composition: "A stateful op declared before .parallel() is still globally correct" — `distinct()` becomes split_point()'s barrier under fork/join, same as it became the racing barrier before |
| test_an_ordinary_terminal_follows_the_streams_executor | guarantee/survives | stream-execution-model: "An ordinary terminal follows the stream's executor" |
| test_for_each_ordered_follows_the_streams_executor_when_ordered | guarantee/survives | stream-execution-model: conditional-observer scenarios |
| test_for_each_ordered_follows_the_streams_executor_when_unordered | guarantee/survives | same — assertion only checks the multiset (`sorted(seen)`), not order, so decision 9's narrowing doesn't even touch it |
| test_find_first_on_an_ordered_parallel_stream_follows_the_executor | guarantee/survives | stream-execution-model: "find_first follows the stream's executor" |
| test_find_first_holds_when_the_op_is_declared_before_parallel | guarantee/survives | same |
| test_find_first_on_an_unordered_stream_is_not_released_by_it | guarantee/survives | stream-execution-model: "find_first is not released by unordered()" — ALWAYS demand still forces a split under fork/join |
| test_both_executors_produce_the_same_elements | guarantee/survives | stream-execution-model: "Both executors produce the same elements" |
| test_the_fused_override_is_indistinguishable_from_the_generic_form | guarantee/survives | stream-execution-model: fused-override scenario — exercises `SEQUENTIAL` only, no racing/fork-join involvement |
| test_racing_uses_the_generic_value_unchanged | **rewrite** | stream-execution-model's "no single chain to fuse a terminal onto" — same conclusion holds for `_ForkJoin` (task 2.6 note: each element gets a fresh sink, still no single chain). Rewrite: `RACING` → `FORK_JOIN`. |
| test_racing_over_an_async_iterator_with_no_aclose | guarantee/survives | stream-execution-model: source-acceptance — empty chain, so this predates and didn't need the `aiter()` fix, but still a real, passing assertion of the guarantee |
| test_racing_over_a_source_whose_aiter_returns_a_separate_iterator | guarantee/survives | stream-execution-model: source-acceptance — **empty chain**, degenerates to `_stream_through([], source)`, so it never exercised `_fork_join_batches()`. `test_fork_join.py::test_parallel_over_a_source_whose_aiter_returns_a_separate_iterator` (new) closes this gap with a non-empty chain and is what actually caught the `aiter()` bug. |
| test_a_closeable_source_is_still_closed_under_racing | guarantee/survives | stream-execution-model: source-acceptance — empty chain |
| test_sync_and_scalar_sources_race_identically (×4 params) | guarantee/survives | stream-execution-model: source-acceptance — empty chain |
| test_a_subclass_taking_one_unrelated_argument_can_be_extended | guarantee/survives | derive-without-reinit; non-empty chain (`.map()`), exercises real fork/join path correctly |
| test_a_subclass_taking_no_arguments_at_all_can_be_extended | guarantee/survives | derive-without-reinit; no `.parallel()` |
| test_subclass_state_is_shared_across_a_pipelines_stages | guarantee/survives | derive-without-reinit; no `.parallel()` |
| test_stream_defines_no_copy_hook | guarantee/survives | derive-without-reinit; no `.parallel()` |
| test_a_subclasss_copy_hook_governs_derivation | guarantee/survives | derive-without-reinit; no `.parallel()` |

**Section total: 27. guarantee/survives: 26. rewrite: 1. mechanism/delete: 0.**

## tests/test_parallel.py (13 tests) — DONE

All 13 currently pass unmodified against `FORK_JOIN` (verified: `pytest
tests/test_parallel.py -v`, 13 passed). None assert a mechanism that no
longer exists; several have racing-specific *comments* worth correcting in a
later cleanup pass, noted below, but that is prose, not a classification
change.

| Test | Verdict | Requirement |
|---|---|---|
| test_parallel_simple | guarantee/survives | pipeline-composition: distinct() global correctness |
| test_parallel_is_faster_than_sequential | guarantee/survives | fork/join genuinely parallelises async I/O-bound work — a real timing claim, not a mechanism assertion |
| test_parallel_distinct_no_cross_branch_duplicates | guarantee/survives | pipeline-composition: cross-branch distinct() dedup — "branch" in the name/comment is now "batch", cosmetic only |
| test_parallel_limit_does_not_exceed_n_across_branches | guarantee/survives | pipeline-composition: limit() cardinality across branches/batches |
| test_parallel_skip_drops_exactly_n_across_branches | guarantee/survives | pipeline-composition: skip() cardinality |
| test_parallel_skip_state_fresh_across_separate_streams | guarantee/survives | pipeline-composition: per-composition state reset |
| test_parallel_distinct_state_fresh_across_separate_streams | guarantee/survives | pipeline-composition: per-composition state reset |
| test_parallel_over_source_with_real_await_empty_chain | guarantee/survives | stream-execution-model: source-acceptance. Comment ("branches would race __anext__ directly... if it weren't guarded") describes RACING's hazard specifically; under fork/join an empty chain takes the empty-head shortcut straight to a single sequential pass, so there is no concurrent access here at all any more. The assertion still correctly checks output correctness — comment needs rewriting in section 6, not the test logic. |
| test_parallel_over_source_with_real_await_nonempty_chain | guarantee/survives | stream-execution-model: source-acceptance under a real chain — this is the shape that actually exercises `_fork_join_batches()` and would have caught the `aiter()` bug had it used a bare `AsyncIterable` rather than an async generator (it uses `_agen_with_real_await`, which already has `__anext__`, so it didn't) |
| test_parallel_limit_with_real_await_source_closes_safely | guarantee/survives | pipeline-composition: safe shared-source close. Comment describes RACING's concurrent-branches-closing hazard specifically; under fork/join all pulls are sequential on the main coroutine (`_pull_round`), so that specific hazard doesn't exist, but the assertion (≤10 elements, no exception) is still a real, worthwhile correctness check. Comment needs rewriting in section 6. |
| test_parallel_downstream_processing_stays_concurrent_with_real_await_source | guarantee/survives | pipeline-composition: "Downstream processing remains concurrent across branches" — comment already describes fork/join's actual shape almost exactly ("pulls... serialized" / "mapper invocations overlap") even though it currently says "branches" |
| test_parallel_applies_to_ops_declared_before_it | guarantee/survives | stream-execution-model: mode-switch position-independence, with a timing check |
| test_parallel_declared_late_still_produces_every_element | guarantee/survives | pipeline-composition: stateful op declared before `.parallel()` stays globally correct |

**Section total: 13. guarantee/survives: 13. rewrite: 0. mechanism/delete: 0.**

## Correction from a peer review, mid-audit

A peer session (which authored this change's design) flagged, and I verified
against the live spec text, that classifying the delivery-order-narrowing
tests as bare "mechanism/delete" was wrong: `racing-encounter-order`'s "An
unordered pipeline takes the order-blind path" requirement is a **live**
requirement stating delivery is order-blind "on any racing pipeline
delivering to an order-observing terminal," which is false under fork/join
for a pipeline with no stateful op. Section 3's own rule ("does it assert a
requirement that survives") means these tests map to a real, still-standing
requirement — deleting them without touching the spec would leave the spec
asserting behaviour the code no longer has, exactly the silent-loss case the
gate exists to catch.

Fixed by writing the `racing-encounter-order` MODIFIED delta now (pulling
forward part of task 5.1) at
`specs/racing-encounter-order/spec.md` in this change, covering the three
requirements the narrowing touches. It removes the delivery-order-relaxation
claim with a stated reason (design.md decision 9, itself corrected per the
same review — see its "found during implementation" note), and keeps the
stateful-op arrival-selection guarantee and `sorted()`'s whole-stream view
intact. `openspec validate` passes against it. The remaining five
requirements in that spec (read-ahead bound, source-acceptance,
verification methodology) are cosmetic-only under fork/join — no requirement
in them goes false, only "branches" → "batches" terminology — and are left
for the full task 5.1 pass in section 5, not touched here.

Below, a test is marked **mechanism/delete** only when it tests dead
machinery unrelated to the delivery-order question (direct `_Window`/
`_guarded`/`_in_flight` probes, the old numeric read-ahead formula). A test
whose assertion is now false specifically because of the delivery-order
narrowing is marked **spec-removed/delete**, naming the scenario in the delta
above it is deleted against — the requirement was modified to remove that
guarantee, so the test isn't losing coverage of something still standing.

**Superseded by the section immediately below.** The `racing-encounter-order`
delta this section describes, and the `spec-removed/delete` verdict it
defines, do not appear in the final tables further down — a second,
independent bug fix reversed most of what this correction was reacting to.
Kept here rather than deleted because it is the accurate record of what was
found and why at the time; treat the delta file in this change's `specs/`
directory and the final per-test tables as authoritative, not this section's
description of them.

## Second correction, found independently while auditing test_racing_delivery_order.py

Running that file's own tests surfaced a separate, more serious bug: order-
blind, short-circuiting terminals (`any_match`, `find_any`, `count`,
`for_each`) — whose demand is `OrderDemand.NONE` unconditionally, regardless
of `unordered()` — waited on a whole batch round via `_fork_join_batches()`'s
original strict `asyncio.gather()`, so `any_match()` over an endless source
with one 5-second element timed out even though the match it wanted was at
index 3. Fixed (design.md decision 10) by making `_fork_join_batches()`
dispatch a round-preserving `gather()` only when `split_point()` finds
something downstream that needs order, and a `FIRST_COMPLETED`-based sliding
window otherwise — no index tagging, no window struct, nothing restoring an
order nobody asked for.

That fix's side effect reverses most of the first correction above.
`split_point()` returns `None` for `.unordered().map(f).collect(to_list())`
for the same reason it does for `count()` — `unordered()` clears the
terminal-clause condition regardless of what the terminal declares — so that
pipeline now *also* gets the `FIRST_COMPLETED` path, and delivery scrambles
again for sources large enough to span more than one batch. Verified: a
20-element source under `.unordered()` now delivers
`[16, 17, 18, 19, 0, 1, ...]`, matching RACING. 17 of the 20 originally-
failing tests pass unmodified against the corrected executor; only 3 of the
delivery-order-narrowing tests are genuinely different now, and it is a test-
fixture-size issue, not a lost guarantee: `test_unordered.py` and
`test_for_each_ordered.py`'s shared `values = [4, 1, 7, 2, 8, 3, 6, 5]`
fixture (8 elements) fits in one batch (`_FIRST_BATCH_SIZE` = 16), so it
never demonstrates scrambling regardless of `unordered()` — RACING's
per-element branching had no such size floor. These are classified
**rewrite** below, not mechanism or spec-removed: the guarantee they assert
still holds, their fixture is too small to show it.

The `racing-encounter-order` delta has been rewritten accordingly (much
smaller than the first attempt): it no longer removes the delivery-order
guarantee, only states the batch-size precondition and the one genuinely new,
bounded exception decision 10 leaves (an order-blind terminal delayed by a
slow element sharing its own batch) as an extension of the read-ahead
requirement's existing over-pull allowance. `openspec validate` passes
against it.

## tests/test_racing_encounter_order.py (44 tests) — DONE

| Test | Verdict | Requirement |
|---|---|---|
| test_an_order_preserving_chain_has_no_split_point | guarantee/survives | tests `split_point()` directly — retained code (design.md decision 3) |
| test_an_empty_chain_has_no_split_point | guarantee/survives | same |
| test_an_order_sensitive_op_at_an_ordered_position_splits (×3: Limit/Skip/Distinct) | guarantee/survives | same |
| test_an_order_sensitive_op_at_an_unordered_position_does_not_split (×3) | guarantee/survives | same |
| test_a_sort_splits_even_at_an_unordered_position | guarantee/survives | same |
| test_the_first_split_point_wins_over_a_later_one | guarantee/survives | same |
| test_an_order_observing_terminal_splits_at_the_end_of_the_chain | guarantee/survives | same |
| test_an_order_blind_terminal_does_not_split | guarantee/survives | same |
| test_an_unordered_pipeline_does_not_split_for_its_terminal | guarantee/survives | same |
| test_an_operations_split_wins_over_the_terminals | guarantee/survives | same |
| test_the_terminal_clause_reads_the_carried_ordering_seed | guarantee/survives | same |
| test_limit_selects_the_first_n_in_encounter_order | guarantee/survives | racing-encounter-order: op-clause selection under encounter order |
| test_skip_drops_the_first_n_in_encounter_order | guarantee/survives | same |
| test_sorted_sorts_across_branches_over_an_async_source | guarantee/survives | racing-encounter-order: `sorted()` sees the whole stream — survives verbatim, `sorted()` is unaffected by decision 9 |
| test_sorted_sorts_across_branches_over_a_sync_source | guarantee/survives | same |
| test_distinct_keeps_the_earliest_encountered_of_each_equal_group | guarantee/survives | racing-encounter-order: op-clause selection |
| test_an_unordered_limit_takes_the_first_n_to_arrive | guarantee/survives | racing-encounter-order (delta): "An unordered limit() takes the first n to arrive" — selection-by-arrival survives; verified empirically (test passes unmodified against `FORK_JOIN`) |
| test_an_unordered_skip_drops_the_first_n_to_arrive | guarantee/survives | same pattern for skip() |
| test_an_unordered_distinct_keeps_an_arbitrary_representative | guarantee/survives | same pattern for distinct(), cardinality only |
| test_an_unordered_pipeline_pays_no_head_of_line_delay | guarantee/survives | racing-encounter-order: "An unordered pipeline pays no ordering cost." Failed against the first (wrong) executor fix, passes against the corrected one (design.md decision 9's second pass) — source is 40 elements, well past the one-batch threshold, so `unordered()`'s concurrency benefit is observable |
| test_unordered_applies_only_to_ops_queued_after_it | guarantee/survives | racing-encounter-order (delta): scenario of the same name |
| test_a_sort_re_imposes_the_requirement_for_what_follows | guarantee/survives | racing-encounter-order (delta): "sorted() re-imposes the requirement for what follows" |
| test_an_order_sensitive_op_queued_before_parallel_is_still_honoured | guarantee/survives | racing-encounter-order: executor governs whole pipeline |
| test_a_sort_queued_before_parallel_is_still_honoured | guarantee/survives | same |
| test_a_barrier_is_not_a_third_mode | guarantee/survives | stream-execution-model: barrier is not a third mode |
| test_a_slow_first_element_does_not_draw_the_whole_source_in | **mechanism/delete** | imports `_in_flight`/`PROCESSES`, asserts the old numeric window formula (`<=16`); fails under fork/join (`64`, the round-level bound). Superseded by `test_fork_join.py::test_in_flight_elements_are_bounded_by_workers_times_batch_size`, which asserts the surviving requirement (bounded read-ahead) against the correct formula |
| test_closing_while_a_branch_is_blocked_on_the_window_does_not_hang | guarantee/survives | safe cancellation while slow work is in flight — genuine correctness property, holds under fork/join's own cancel-on-failure path (`_run_round`), mechanism differs entirely but the guarantee does not. Comment ("window") is racing-specific prose, cosmetic |
| test_a_wider_race_is_given_a_wider_window | **mechanism/delete** | directly constructs `execution._Racing(wide)`, imports `_in_flight` — no fork/join analogue in the same shape (worker count scaling relationship differs) |
| test_over_pull_upstream_of_an_ordered_limit_is_bounded | **mechanism/delete** | imports `_in_flight`, asserts old formula; fails under fork/join (`64`). Superseded by `test_fork_join.py::test_limit_under_parallel_does_not_pull_a_full_batch_size_per_worker` |
| test_an_ordered_limit_over_an_unbounded_source_terminates | guarantee/survives | racing-encounter-order: read-ahead bound requirement, termination scenario |
| test_a_barrier_does_not_change_how_the_shared_source_is_closed | guarantee/survives | racing-encounter-order: ordering doesn't change source-close count |
| test_a_generator_source_behind_a_barrier_runs_its_finally_once | guarantee/survives | same |
| test_a_source_with_no_aclose_still_races_behind_a_barrier | guarantee/survives | racing-encounter-order: source acceptance under a barrier |
| test_every_element_appears_exactly_once_behind_a_barrier | guarantee/survives | racing-encounter-order: no loss/duplication |
| test_a_flat_map_upstream_of_a_barrier_keeps_every_output | guarantee/survives | same; matches task 2.2's own flat_map verification |
| test_a_filter_upstream_of_a_barrier_does_not_stall_the_merge | guarantee/survives | same — trivially true under fork/join, no merge to stall at all |
| test_an_error_upstream_of_a_barrier_propagates_rather_than_hanging | guarantee/survives | racing-encounter-order: error propagation; matches task 2.5 |
| test_a_head_op_that_emits_at_end_is_ordered_after_every_real_group | **mechanism/delete** | constructs `_Window`, `_guarded`, `_group_through`, `_release_in_order` directly — no fork/join counterpart, these primitives are deleted in section 4 |
| test_a_cancelling_head_op_stops_its_branch_without_stalling_the_merge | guarantee/survives | limit at an unordered position cancels within a batch; sort (barrier) still sees every admitted element |
| test_branches_contending_for_the_last_window_slot_still_pull_in_order | **mechanism/delete** | monkeypatches `execution._in_flight` directly — the window-slot contention scenario has no fork/join analogue (batches are pulled sequentially, no contention) |
| test_a_head_cancelled_before_its_first_pull_yields_nothing | guarantee/survives | limit(0) at an unordered position cancels from `begin()`; `_run_element`'s fresh-sink-per-element naturally reproduces this. Comment overstates ("must not pull even once" — a batch of raw elements is still pulled from source before per-element cancellation is discovered) but the assertions (`res == []`, `seen == []`) hold |
| test_a_racing_sort_is_stable (×3 params) | guarantee/survives | comparator-contract / racing-encounter-order: sort stability |
| test_a_sort_on_an_unordered_pipeline_is_stable (×3 params) | guarantee/survives | same |
| test_an_unordered_sort_sorts_the_whole_stream_not_per_branch_subsets | guarantee/survives | racing-encounter-order (delta): "An unordered sort still sorts the whole stream" |

**Section total: 44. guarantee/survives: 39. mechanism/delete: 5.**

## tests/test_racing_delivery_order.py (41 tests) — DONE

Verified: 38 of 41 pass unmodified against the corrected executor. 3 need
attention — 2 fixture-size **rewrites** (design.md decision 9's second pass:
their sources are small enough to fit in one batch, so they no longer
demonstrate the `unordered()` scrambling their assertion depends on) and 1
old-formula **mechanism/delete**, superseded by `test_fork_join.py`.

| Test | Verdict | Requirement |
|---|---|---|
| test_an_ordered_racing_map_delivers_in_encounter_order | guarantee/survives | racing-encounter-order: delivers in encounter order |
| test_an_ordered_racing_pipeline_matches_the_sequential_result | guarantee/survives | same, through filter+flat_map |
| test_an_async_source_delivers_in_encounter_order_too | guarantee/survives | same |
| test_reduce_folds_in_encounter_order | guarantee/survives | racing-encounter-order: reduce() folds in encounter order |
| test_to_array_delivers_in_encounter_order | guarantee/survives | racing-encounter-order: to_array() observes order |
| test_the_three_argument_collect_delivers_in_encounter_order | guarantee/survives | racing-encounter-order: 3-arg collect() observes order |
| test_iterator_yields_in_encounter_order | guarantee/survives | racing-encounter-order: iterator() observes order |
| test_to_generator_yields_in_encounter_order | guarantee/survives | same, via to_generator |
| test_for_each_does_not_wait_for_encounter_order | guarantee/survives | racing-encounter-order: order-blind terminal — SOURCE is 20 elements, spans multiple batches, scrambling observable |
| test_count_is_unaffected | guarantee/survives | racing-encounter-order: order-blind terminal pays nothing |
| test_an_order_blind_terminal_holds_nothing_back | **rewrite** | racing-encounter-order (delta): "An order-blind terminal may be delayed by its own batch" — target index 3 collides with the slow index-0 element in the same first batch (decision 10's accepted, bounded exception). Rewrite with a target index past the first batch boundary, matching `test_fork_join.py`'s new regression test |
| test_find_any_still_races | guarantee/survives | racing-encounter-order: find_any() races |
| test_min_and_max_are_unaffected | guarantee/survives | racing-encounter-order: max()/min() order-blind cost |
| test_to_set_takes_the_order_blind_path | guarantee/survives | racing-encounter-order: UNORDERED collector declaration guard |
| test_grouping_by_into_an_unordered_downstream_skips_the_barrier | guarantee/survives | same, recording downstream — SOURCE=20, spans batches |
| test_grouping_by_with_a_map_factory_takes_the_barrier | guarantee/survives | mirror: a map_factory clears UNORDERED |
| test_grouping_by_into_a_set_collects_correctly_under_racing | guarantee/survives | correctness under racing |
| test_partitioning_by_into_an_unordered_downstream_skips_the_barrier | guarantee/survives | same pattern for partitioning_by |
| test_partitioning_by_into_a_set_collects_correctly_under_racing | guarantee/survives | correctness under racing |
| test_to_map_without_a_merge_function_skips_the_barrier | guarantee/survives | dict key-iteration-order observation of the order-blind path |
| test_to_map_with_a_merge_function_keeps_its_barrier | guarantee/survives | mirror: merge_function form keeps its barrier |
| test_to_map_raises_on_a_duplicate_key_under_either_executor | guarantee/survives | property of elements, not order |
| test_equality_not_iteration_order_is_what_a_declarer_must_meet | guarantee/survives | no `.parallel()` involved at all |
| test_two_collectors_differing_only_in_unordered_deliver_differently | guarantee/survives | SOURCE=20, spans batches |
| test_a_declaring_collector_is_unaffected_under_sequential | guarantee/survives | sequential executor only |
| test_unordered_removes_the_delivery_barrier | guarantee/survives | racing-encounter-order (delta): "An unordered pipeline with no order-sensitive operation pays no delivery cost" — SOURCE=20 |
| test_unordered_is_faster_than_the_ordered_form | guarantee/survives | same, timing — 40-element source |
| test_ordered_delivery_still_runs_the_chain_concurrently | guarantee/survives | delivery ordering doesn't serialize the chain |
| test_the_suffix_of_a_short_circuiting_pipeline_races | guarantee/survives | resumed tail races |
| test_a_raced_suffix_still_delivers_in_encounter_order | guarantee/survives | same |
| test_a_tail_that_sorts_again_splits_again | guarantee/survives | nested barrier |
| test_unordered_in_the_tail_removes_the_delivery_barrier | guarantee/survives | racing-encounter-order (delta): same scenario. Failed against the pre-fix `_FIRST_BATCH_SIZE` (16, off by `workers`); passes unmodified once that's corrected to 4 (design.md decision 1's "made concrete" note) — a 12-element source now spans multiple batches |
| test_is_parallel_still_reports_the_executor_under_a_delivery_barrier | guarantee/survives | stream-execution-model: barrier is not a third mode |
| test_a_delivery_barrier_does_not_change_how_the_source_is_closed | guarantee/survives | ordering doesn't change source-close count |
| test_a_generator_source_under_a_delivery_barrier_runs_its_finally_once | guarantee/survives | same |
| test_an_error_under_a_delivery_barrier_propagates_without_hanging | guarantee/survives | error propagation under a barrier |
| test_read_ahead_under_a_delivery_barrier_is_bounded | **mechanism/delete** | imports `_in_flight`/`PROCESSES`, old numeric formula (`<=16`), fails under fork/join (`64`). Superseded by `test_fork_join.py::test_in_flight_elements_are_bounded_by_workers_times_batch_size` |
| test_counting_takes_the_order_blind_path | guarantee/survives | UNORDERED declaration guard |
| test_summing_int_takes_the_order_blind_path | guarantee/survives | same |
| test_summarizing_int_takes_the_order_blind_path | guarantee/survives | same |
| test_summing_double_is_delivered_in_encounter_order | guarantee/survives | unmarked collector takes the barrier |

**Section total: 41. guarantee/survives: 39. rewrite: 1. mechanism/delete: 1.**
(revised again — see "Third correction" below)

## Scattered references (5 files + conftest.py) — DONE

Design.md's Risks section named these as carrying scattered references
outside the four primary files. Verified: `tests/test_fork_join.py` (this
session's new file) also references `RACING`/`FORK_JOIN`/`PROCESSES` but is
not part of this audit — it is new, additive coverage, not an inherited
mechanism test.

| File | What's there | Verdict |
|---|---|---|
| `tests/conftest.py` | One comment: "with PROCESSES branches, a slow head is..." | prose only — reword `branches` → `workers`/`batches` when touched in section 4/6, no functional change |
| `tests/test_find_first.py` | Imports `PROCESSES, _in_flight`; `test_a_parallel_find_first_may_process_more_than_one_element` asserts `1 < len(calls) <= _in_flight(PROCESSES)` | guarantee/survives, but **rewrite for the import**: passes unmodified once `_FIRST_BATCH_SIZE`'s off-by-`workers` bug is fixed (design.md decision 1's "made concrete" note — round 1's true total is 16, matching `_in_flight(4)` exactly), but `_in_flight`/`PROCESSES` are still deleted in section 4, so the assertion's *expression* needs swapping to the new bound even though its *value* already agrees. `test_find_any_remains_the_unordered_alternative` asserts `len(seen) < len(values)` (partial visitation) over the 8-element `values` fixture — **rewrite**, still fails: `find_any()`'s all-in-one-round dispatch (decision 10's accepted intra-batch/in-flight-fill exception) processes every element before returning when the whole source fits within the initial `workers`-batch fill, same as `test_an_order_blind_terminal_holds_nothing_back` above |
| `tests/test_for_each_ordered.py` | One comment ("the pipeline would run unordered under RACING with no barrier"); 2 tests over the shared 8-element `values` fixture | Comment: reword in section 6 (prose only). `test_for_each_on_parallel_stream_can_be_out_of_order` and `test_for_each_ordered_on_unordered_parallel_stream_does_not_deliver_in_order` — guarantee/survives, pass unmodified once the `_FIRST_BATCH_SIZE` bug (above) is fixed: 8 elements now span 2 batches of 4 |
| `tests/test_name_visibility.py` | Asserts a specific internal-name-visibility finding naming `_in_flight` (`snakestream.execution`) | **rewrite** — the assertion must track whatever internal names section 4 actually leaves behind once `_in_flight`/`_IN_FLIGHT_PER_WORKER` are deleted; mechanical update in section 4, not a guarantee loss |
| `tests/test_package_exports.py` | Asserts `PROCESSES` is not publicly exported; asserts `_in_flight`/`_IN_FLIGHT_PER_WORKER` have no public name | **rewrite** — the *requirement* (racing-encounter-order: "the read-ahead bound is not part of the public surface") survives; the *names* it's checked against change (`PROCESSES` → `WORKERS`, task 4.6; `_in_flight`/`_IN_FLIGHT_PER_WORKER` deleted outright rather than renamed) |
| `tests/test_unordered.py` | Imports nothing mechanism-specific; 2 tests (`test_unordered_clears_the_encounter_order_requirement`, `test_unordered_after_sorted_is_unordered`) over the shared 8-element `values` fixture | guarantee/survives, pass unmodified once the `_FIRST_BATCH_SIZE` bug (above) is fixed |

**Scattered total (revised, see Third correction below): 6 files.
guarantee/survives: 5 tests. rewrite: 2 tests + 1 import swap
(`test_a_parallel_find_first_may_process_more_than_one_element`) + 2 files'
assertions (name_visibility, package_exports) + 2 comments (prose only, not
counted as tests).**

## Third correction: `_FIRST_BATCH_SIZE` was off by `workers`

A peer review, again — this time catching an arithmetic slip rather than a
design question. `_FIRST_BATCH_SIZE` was set to `16`, meant to match
`_in_flight(PROCESSES)` (`_IN_FLIGHT_PER_WORKER × workers` = `4 × 4` = `16`,
a *total*) "in order of magnitude." But `_pull_round()` already multiplies by
`workers` once — it pulls up to `_FIRST_BATCH_SIZE` elements **per worker**,
`workers` times — so round 1's real total was `16 × 4` = `64`, not `16`.
Fixed: `_FIRST_BATCH_SIZE = _IN_FLIGHT_PER_WORKER` (a definition, not a new
magic number), giving `4 × 4 = 16` exactly. See design.md decision 1's "made
concrete" addendum.

This one constant explains nearly every remaining failure from the "Second
correction" pass above. Re-running the full suite after the fix: **2
failures, down from 11.** Both are the genuinely new, accepted, bounded
exception (design.md decision 10; the read-ahead-bound delta's "An
order-blind terminal may be delayed by its own batch" scenario) —
`test_an_order_blind_terminal_holds_nothing_back` and
`test_find_any_remains_the_unordered_alternative` both use a source small
enough that every batch is dispatched in the initial fill, before any can be
skipped. The other 9 tests I had classified `rewrite` for fixture size — 2 in
`test_racing_delivery_order.py`, 2 in `test_unordered.py`, 2 in
`test_for_each_ordered.py`, `test_find_any_remains_the_unordered_alternative`'s
sibling `test_a_parallel_find_first_may_process_more_than_one_element` — pass
**unmodified** against the corrected constant. Per-row corrections are made
in each section's table above rather than left for a reader to reconcile
against this note.

## Grand total (task 3.4: the three counts reconciled against the inventory)

| Source | Total | guarantee/survives | rewrite | mechanism/delete |
|---|---|---|---|---|
| test_execution_model.py | 27 | 26 | 1 | 0 |
| test_parallel.py | 13 | 13 | 0 | 0 |
| test_racing_encounter_order.py | 44 | 39 | 0 | 5 |
| test_racing_delivery_order.py | 41 | 39 | 1 | 1 |
| **Primary four files** | **125** | **117** | **2** | **6** |
| scattered (6 files, affected tests only) | 8 | 5 | 3 | 0 |

125 (primary four) matches design.md's stated inventory count exactly.
117 + 2 + 6 = 125: every test in the primary four files is accounted for by
exactly one verdict. Only 2 tests in the entire 125-test inventory need an
actual behavioural rewrite going into section 4
(`test_an_order_blind_terminal_holds_nothing_back`,
`test_find_any_remains_the_unordered_alternative`, both against a fixture
past the initial-fill boundary, matching `test_fork_join.py`'s existing
regression test for the same exception); everything else marked `rewrite`
in the scattered-files table is a mechanical name swap (`PROCESSES` →
`WORKERS`, `_in_flight` deleted), not a guarantee loss.

## Section 4 outcome (task 4.7's post-deletion re-check)

Both behavioural rewrites landed and were verified to catch a deliberately
reverted fix (forcing `_fork_join_ordered_batches` unconditionally reproduces
the exact hang/timeout the original bug had). All 6 mechanism tests in the
primary files and the superseded scattered-file test were deleted. The
mechanical renames (`PROCESSES`→`WORKERS`, `_in_flight`/`_IN_FLIGHT_PER_WORKER`
deleted outright, `test_name_visibility.py`/`test_package_exports.py`
updated to match) landed alongside the machinery deletion itself, since the
imports would otherwise break at collection time.

`execution.py`: `_Window`, `_guarded`, `_group_through`, `_releasable`,
`_release_in_order`, `_run_ordered_tail`, `_racing_branches`, `_race_through`,
`_IN_FLIGHT_PER_WORKER`, `_in_flight()`, `_Racing`, `RACING` all deleted;
module docstring rewritten. `_guarded` had no callers left outside
`_race_through` (also deleted) once fork/join's own source-pull went through
`_pull_round()`/`batch()` instead, so it was deleted whole rather than only
its windowed branch, as tasks.md's original wording anticipated a partial
deletion that turned out not to be needed.

A sweep for every deleted name across `src/` and `tests/` found two source
docstrings (`stream.py`'s `_accept()`, `ordering.py`'s `split_point()`) that
named `_guarded`/`_race_through` as if they still existed — a real
documentation bug the sweep exists to catch, fixed in the same pass. Every
remaining mention of `RACING` or a deleted function name is historical prose
(explicitly framed as "no longer exists" / "used to") or an intentional
absence-check (`test_package_exports.py`).

Final state: 1033 passed, `ruff check .` and `ty check src` clean, coverage
99% (not used as evidence per task 4.7's own instruction against trusting the
coverage gate here — the reference sweep above is what actually verifies
nothing was silently orphaned). `openspec validate` reports valid.
