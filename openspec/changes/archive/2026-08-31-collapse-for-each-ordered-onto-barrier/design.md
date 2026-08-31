## Context

See `proposal.md` — Why. The mechanism this change moves onto already exists,
is already exercised by every other order-observing terminal, and needs no
modification: `_split_point()`'s third clause is `observes_order and
is_ordered(chain)`, and `for_each_ordered()` computes that same condition by
hand before choosing an executor.

The only design content here is what *not* to touch, because this change is the
first of a pair. `collapse-find-first-onto-barrier` lands second and rests on
what this one leaves in place.

## Goals / Non-Goals

**Goals:**

- Delete the hand-rolled branch at one call site, changing no shared machinery.
- Leave the codebase in a state where the second change is a clean diff rather
  than a rebase against half-applied work.

**Non-Goals:**

- Removing `_evaluate()`'s `executor` parameter. `find_first()` is still a
  caller after this change; the parameter goes in the second change.
- Removing `Stream._is_ordered()` or the `SEQUENTIAL` import in `stream.py`.
  Both survive *both* changes — `Stream.concat()` uses them at `stream.py:402`.
  The roadmap's "what disappears" list is wrong on these two entries and the
  proposal records the correction.
- Widening `observes_order` to the three-valued demand. `for_each_ordered()`'s
  demand is conditional, so `True` expresses it exactly; the widening is the
  second change's, driven by `find_first()`'s unconditional one.

## Decisions

**Delete the branch rather than reroute it.** `for_each_ordered()` becomes:

```python
return await self._evaluate(_ForEachSink(consumer), True)
```

which is `for_each()` with `True` where it passes `False` — the entire
difference between the two operations, which is what the pair should look like.

*Alternative considered:* keep the `_is_ordered()` call and pass its result as
`observes_order` (`self._evaluate(sink, self._is_ordered())`). This is wrong in
a way worth recording: `observes_order` is a claim about the *terminal*, not
about the pipeline. `for_each_ordered()` observes encounter order whatever the
chain says; whether that demand is *satisfiable* is `_split_point()`'s question,
and it already asks it. Threading the chain's characteristic through the
terminal's declaration would put the same fold on both sides of the call and
re-introduce, in a subtler form, the coupling this change removes.

**Rewrite the docstring's Java citation.** The current one cites
`ForEachOps.OfRef.evaluateParallel()` picking `ForEachOrderedTask` or
`ForEachTask`, which is accurate and was the justification for the branch. The
citation that matters now is one step further in: `ForEachOrderedTask` is itself
a `CountedCompleter` over the fork-join pool. Java's ordered path stays
parallel, so the branch was never porting Java's shape — it was porting the
*decision* Java makes and then implementing the ordered side differently.

**Sequence this change first.** Both changes touch the `terminal-sinks`
requirement "An ordered drive is available regardless of stream mode": this one
restates it with `find_first()` as its only user, the next deletes it. In this
order each delta applies to the spec state its predecessor leaves. In the other
order, this change would restate a requirement that no longer exists, and
`openspec validate` would not catch it — it does not check REMOVED or MODIFIED
headers against the main specs.

## Risks / Trade-offs

**A timing-based test for "the chain still races" is flaky by construction** →
Assert on invocation overlap rather than on wall clock: have the mapper record
entry and exit timestamps and assert that at least two intervals overlap. That
is the actual claim, it does not depend on a threshold, and it fails for the
right reason if the chain is serialized. Keep any wall-clock assertion loose
(e.g. "less than half the sequential time" on a 4-worker chain of equal-cost
sleeps) and out of the coverage-gated path if it proves unstable.

**Upstream side effects change order silently for existing callers** → The
README migration-log entry is the mitigation, and it is not optional: a caller
who put a counter or a logger in `peek()` upstream of `for_each_ordered()` gets
the same values in a different order with no error. The `stream-foreach-ordered`
delta states the guarantee's boundary explicitly (the consumer, and nothing
before it) so the contract answers the question the migration entry raises.

**An ordered `for_each_ordered()` now buffers** → It engages the delivery
barrier, so it holds finished elements until earlier ones are released, bounded
by `_READ_AHEAD`. Previously it held nothing because it ran single-flight. This
is the same trade every other order-observing terminal already makes and is
measured in `race_through()`'s docstring; `unordered()` remains the lever.

## Migration Plan

Single commit, no staged rollout — a library change with no persisted state.
Rollback is a revert. The README migration-log entry lands in the same commit as
the behaviour change, per project convention.
