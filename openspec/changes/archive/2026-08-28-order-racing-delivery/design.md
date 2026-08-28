## Context

See proposal.md — Why. The machinery this change extends already exists and
mostly does not move: `_guarded()` assigns source indices under the lock,
`_Window` bounds read-ahead, `group_through()` yields `(index, outputs)`, and
`_release_in_order()` reorders at the merge. `order-stateful-ops-under-racing`
built all of it to serve one caller — an order-sensitive *operation* at
`_split_point(chain)`. This change adds a second caller, the *terminal*, and
replaces the rule that decides how much of the tail races.

Two constraints shape the approach:

- `execution.py` may not import `stream.py`. The ordering demand has to arrive
  as a plain value on the executor protocol, not as something read off a stream.
- `is_ordered(chain, upto)` folds from `True`. Any recursive re-entry into
  `race_through()` over a chain *suffix* re-seeds that fold, and would read a
  suffix of an unordered pipeline as ordered.

## Goals / Non-Goals

**Goals:**

- One barrier mechanism serving both callers, with the terminal expressed as a
  split at `len(chain)` rather than as a separate code path.
- The ordering demand carried as one boolean through `Executor` -> `race_through`
  -> `_split_point`, with no new type and no new executor.
- The recursive re-entry made correct with respect to the ordering fold.

**Non-Goals:**

- Changing `find_first()` or `for_each_ordered()`; see proposal Non-goals.
- Marking additional collectors `UNORDERED`; see proposal Non-goals.
- Exporting or renaming `_READ_AHEAD`.
- Any change to `Sink`, `Op`, or the sinks in `ops.py`.

## Decisions

### The terminal barrier is a split at `len(chain)`, not a separate path

`_split_point()` gains a final clause: with no op-based split, if the consumer
observes order and `is_ordered(chain)`, return `len(chain)`. `race_through()`'s
existing split branch then does the right thing unchanged — head is the whole
chain, raced under `group_through()`/`_guarded(window)`, `_release_in_order()`
reorders, and the tail is empty, so `_run_ordered_tail([], ...)` passes the
reordered stream straight out.

*Alternative rejected:* a distinct `_ordered_delivery()` wrapper around
`race_through()`'s unordered merge. It would duplicate the buffer, the window
and the branch clean-up, and would leave two reorder implementations to keep in
step. Expressing delivery as "the split is at the end" is what makes it one
mechanism.

*Consequence:* an ordered racing pipeline that today races end to end now runs
its whole chain under `group_through()` rather than `stream_through()`. The
per-element difference is a list copy and clear per accepted element, which
`group_through()` already does; measurement task 8 owns confirming it.

### The ordering demand is one boolean on the executor protocol

`Executor.elements(chain, source, observes_order)` and
`Executor.value(chain, source, terminal, observes_order)`.
`Sequential` accepts and ignores it — it is ordered by construction.
`Racing` passes it to `race_through()`, which passes it to `_split_point()`.

*Alternative rejected:* asking the terminal sink, e.g. a
`TerminalSink.observes_order` class attribute read inside `race_through()`. It
reads well but does not serve `elements()`, which has no terminal sink at all
and whose consumer — `iterator()`, `to_generator`, `concat()` — always observes
order. One value on both operations keeps the two-operation protocol symmetric,
which the `stream-execution-model` spec requires.

*Where the value comes from:* `Stream._evaluate()` gains an `observes_order`
parameter that each terminal passes explicitly — every terminal states its own
answer at its own call site, which is the same posture `find_first()` already
takes with its executor. `iterator()` passes `True`. `collect(collector)` passes
`Characteristics.UNORDERED not in collector.characteristics`.

### The ordering fold is seeded, not restarted

`is_ordered(chain, upto)` gains an `initial: bool = True` parameter, and
`race_through()` gains an `ordered_in: bool = True`, threaded into
`_split_point(chain, observes_order, ordered_in)` and into the recursive
`race_through()` call for a resumed tail.

This is a latent correctness bug today, not only a new one: on
`.sorted(c).unordered().limit(3)` the current `_resume_point()` resumes at the
`limit`, and `_split_point([limit])` folds from `True` and installs a barrier
the pipeline does not want. The recursion becomes far more common under this
change, so seeding the fold is a prerequisite rather than a tidy-up.

### `_resume_point()` is deleted; the tail is `[barrier] + race(rest)`

Once delivery is reordered at the terminal, the objection `_resume_point()`
encoded — that racing an order-blind suffix scrambles delivery — no longer
holds. `_run_ordered_tail()` becomes: run `tail[0]` alone through
`stream_through()`, then hand `tail[1:]` to `race_through()` with the ordering
state after `tail[0]`. An empty tail (the terminal-barrier case) or a
single-element tail yields the ordered stream directly, with nothing left to
race.

Because the resumed race re-enters `_split_point()` with the same
`observes_order`, a suffix delivering to an order-observing terminal installs
its own delivery barrier — which is what keeps
`.sorted(c).map(f).collect(to_list())` sorted.
`.limit(n).map(fetch).collect(to_list())` therefore pays two barriers: the one
at `limit` and the one at delivery. That is the price of the concurrency the
suffix gains, and it is bounded the same way.

*Alternative rejected:* racing the suffix only when the terminal is order-blind.
It would avoid the second barrier but reintroduce the very seam this change
exists to close — the same pipeline behaving differently depending on the
terminal's declaration in a way the caller cannot see.

### `unordered()` keeps its op and gains no machinery

No change to `_UnorderedOp` or `Ordering.CLEAR`. A pipeline unordered at the
end of the chain simply fails `is_ordered(chain)` in the new `_split_point()`
clause, and the delivery barrier is not installed. This is the whole of the
opt-out.

## Risks / Trade-offs

- **[Every ordered racing pipeline now buffers and blocks at the head.]** The
  default case gets slower and holds up to `_READ_AHEAD` groups in memory.
  → Bounded by the existing window; `unordered()` is the documented lever and
  must be shown measurably faster (task 8). If the default regression is worse
  than the concurrency it preserves, that is a finding to report before landing,
  not something to absorb.

- **[Two barriers on a pipeline with a mid-chain barrier and an ordering
  terminal.]** `.limit(n).map(f).collect(to_list())` reorders twice.
  → Correct, and the second barrier sits over a chain that would otherwise not
  race at all. Measured in task 8 against today's serialized tail.

- **[Behaviour break.]** Callers relying on the scramble get ordered results.
  → README migration log, and `unordered()` restores the old behaviour exactly.

- **[Deadlock surface widens.]** The window/merge pair now runs on pipelines
  that never touched it. → The existing error-propagation and close-count
  scenarios are extended to the delivery-barrier shape rather than assumed to
  carry over.

- **[Empty head raced across N branches.]** With a barrier at index 0 the head
  chain is `[]`, and N branches each run `group_through([])` — pure pull-and-tag
  contention on the lock for no work. This is today's behaviour and is
  unchanged; it is the shape task 8 should watch for a regression on.

## Migration Plan

Single change, no staged rollout. `unordered()` is the rollback for a caller who
wants the old delivery behaviour, and is spec'd as such. The migration log entry
in README is part of the change.
