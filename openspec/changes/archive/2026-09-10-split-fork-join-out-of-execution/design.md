## Context

`execution.py` holds three things at once: the sink-driving primitives, the
fork/join batch machinery, and the `Executor` protocol with its two values. See
proposal.md — Why for the motivation and the line counts.

The one constraint that shapes everything below is a dependency cycle that any
naive two-way split walks straight into:

```
  _ForkJoin.elements()  -->  _fork_join_through()   (the parallel dispatch)
                                      |
                                      v
                             _stream_through()      (the barrier's single
                                      ^              ordered pass, L498/L501)
                                      |
  _Sequential.elements() -------------+
```

`_fork_join_through()` needs `_stream_through()` to run the barrier op over the
concatenated batch output, and `_ForkJoin` needs `_fork_join_through()`. Move
fork/join to its own module and leave the primitives where they are, and
`execution.py` and `fork_join.py` import each other.

## Goals / Non-Goals

**Goals:**
- Each of the three modules shows one concern, with every import edge
  one-directional.
- The fork/join duplications collapse *because* they are now visible together,
  not as a separate act of tidying.
- Zero per-element cost. Every extraction below runs once per round or once per
  composition.

**Non-Goals:**
- No change to the `Executor` protocol's shape, to `OrderDemand`, to
  `split_point()`, or to any sink.
- No change to `stream.py`'s imports. `Executor`, `SEQUENTIAL` and `FORK_JOIN`
  stay in `execution.py` precisely so the split is invisible above it.
- No re-litigation of `_Sequential.value()`'s fused-push override, of the
  ramp's factor of 8, or of `WORKERS = 4`. Those are measured decisions
  (`decisions.md`: `ramp-batch-growth-geometrically`,
  `spread-small-sources-across-workers`) and this change carries them across
  unmodified.
- No new benchmark gate. See Risks.

## Decisions

### 1. Three modules, not two

```
      sink.py     ordering.py     spliterator.py     type.py
            \          |               |            /
             v         v               v           v
                        pipeline.py                          118 lines
                        Java's AbstractPipeline, literally:
                        wrap_sink() / _copy_into(), plus the
                        three drive shapes
                          ^                       ^
                          |                       |
       wrap_sink      x1  |                       |  stream_through  x1
       maybe_aclosing  x2 |                       |  feed_through    x1
       stream_through  x2 |                       |  drain           x1
                          |                       |
                  fork_join.py  <--------------  execution.py
                  390 lines        WORKERS        126 lines
                  the batch and    fork_join_     Executor,
                  partition        through        _Sequential,
                  runners, the     fork_join_     _ForkJoin,
                  round loops,     partitioned    SEQUENTIAL,
                  the split/                      FORK_JOIN
                  barrier recursion                    |
                                                       v
                                                  stream.py  (unchanged)
```

**This is a triangle, not a stack.** `execution.py` does not reach `pipeline.py`
*through* `fork_join.py`; it imports three names from it directly, because
`_Sequential`'s body is `stream_through()`/`feed_through()` and
`Executor.value()`'s generic form is `drain()`. The triangle is forced rather
than chosen: any acyclic arrangement of a sequential implementation, a parallel
implementation, and a protocol that picks between them has this shape, and
moving code between the three nodes relabels them without changing it.

The one name on both upward edges is `stream_through()`, and that is
load-bearing rather than incidental: `fork_join.py` uses it at the order
barrier, where a fork/join pipeline degenerates to a single sequential pass
over the concatenated batch output. The `fork_join -> pipeline` edge therefore
encodes an algorithmic fact — fork/join *contains* sequential execution as a
sub-case — not a reach into a utility bag.

The cycle in Context dissolves once the primitives sit *below* both consumers
rather than beside one of them. `pipeline.py` knows nothing about executors;
`fork_join.py` knows nothing about `Executor`; `execution.py` is the only
module that names both, which is exactly what an executor value is for.

**Rejected: two modules with a deferred import.** Keep the primitives in
`execution.py` and have `_ForkJoin.elements()` do
`from snakestream.fork_join import fork_join_through` inside the method body.
It works, and it hides a genuine cycle behind an import statement placed to
dodge it — the smell the split exists to remove, reintroduced at the one edge
that matters.

**Rejected: two modules with the barrier pass injected.** Pass
`stream_through` into `fork_join_through()` as a parameter so `fork_join.py`
imports nothing from `execution.py`. This breaks the cycle honestly but at the
cost of a parameter that has exactly one possible argument at every call site,
forever — a seam with no second implementation behind it. The recursion at
L501 would have to thread it too.

**Rejected: leave the primitives in `execution.py` and move only the
executors** to a new `executor.py`. Same three-layer stack, but
`execution.py`/`executor.py` as sibling names differing by two letters is a
worse outcome than a rename, and `stream.py` would have to change its imports
for no reason a reader of `stream.py` can see.

### 2. Module names: `pipeline.py`, `fork_join.py`, `execution.py` unchanged

`pipeline.py` is the Java-parity name and not a coinage: `wrap_sink()` and
`_copy_into()` are ports of `AbstractPipeline.wrapSink()` and
`AbstractPipeline.copyInto()`, and both docstrings already say so verbatim
("Java's AbstractPipeline.wrapSink() does exactly this"). It names the concept
rather than a container word, the move `ordering.py` and `unseeded.py` both
made.

`fork_join.py` matches the executor it holds (`_ForkJoin`, `FORK_JOIN`) and
Java's own `ForkJoinTask`/`ForkJoinPool` vocabulary, which the fork/join
docstrings in `execution.py` already borrow from throughout.

Considered and rejected for the primitives module:
- `drive.py` — a verb with no Java counterpart, and "drive" is already
  overloaded in the existing docstrings for what a *terminal* does to a chain.
- `sink_drive.py` / `pipeline_ops.py` — container words glued to a concept,
  the shape the module-naming rule exists to prevent.
- Folding the primitives into `sink.py` — `sink.py` is the protocol (`Sink`,
  `Op`, and the four sink shapes); it does not run anything, and
  `extract-unseeded-fold-module` closed on precisely the principle that a
  protocol module should not accrete the machinery that consumes it.

One caveat this accepts: `pipeline.py` sits next to an existing spec named
`pipeline-composition`, whose subject is exactly `wrap_sink()`. That is
alignment, not collision — but it is the reason the rename touches spec text
at all (see Open Question).

### 3. `gather_or_cancel(tasks)` — the cancel-siblings idiom, once

Three sites carry this verbatim and a fourth carries it over `in_flight`:

```
    try:
        return await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
```

This is not the "thin helper earns nothing" shape (a lone check-and-raise,
where centralizing the *message* or the *type* is the real fix). It is a
six-line concurrency protocol with three separately-gettable-wrong parts —
cancel every sibling, drain them with `return_exceptions=True` so none is left
with an unretrieved exception, re-raise the *original* rather than a wrapper —
and each of the three existing docstrings spends a paragraph re-explaining
those three parts. One helper carries that paragraph once.

It stays private to `fork_join.py`, so it keeps its underscore.

The fourth site (`_fork_join_unordered_batches`'s `except`) has a different
shape: it cancels a live window on the way out of a generator rather than
awaiting a completed gather. It does **not** get folded in — forcing one
signature over both would parameterize away the difference that matters. It
gains a comment pointing at the helper instead, which is what the current
three-way pointer comment should have been.

### 4. `_rounds(src, workers)` — the round loop and the ramp, once

Two loops run the identical skeleton (seed, pull, dispatch, consume, stop on a
short round, ramp) and differ only in what they do with a round's results.
Extracting the skeleton as an async generator leaves each caller with its
genuinely different half:

```
    async def _rounds(source, workers):
        size = 1
        while True:
            round_batches = await _pull_round(source, workers, size)
            if not round_batches:
                return
            yield round_batches
            if len(round_batches) < workers:
                return
            size = min(size * 8, BATCH_SIZE)
```

`_fork_join_ordered_batches()` drops from 7 statements to 4;
`_fork_join_partitioned()`'s inner loop drops to the merge fold. The ramp's
long comment — currently written once and pointed at twice — moves here and is
true in one place.

**One behaviour question this must not answer by accident.**
`_fork_join_partitioned()`'s loop guard is a *pre-first-pull* check
(`while not head.cancellation_requested():`, `# pragma: no branch`), and its
comment states the requirement explicitly: a terminal cancelled before it has
merged anything must not pull even one batch. An `async for` over `_rounds()`
pulls round one *before* the body runs, which would silently drop that
guarantee. The extraction therefore keeps an explicit guard before the loop and
a `break` at the end of the body, preserving both the semantics and the
pragma. Today no terminal reaches it — none of the partitioning terminals
short-circuits — which is exactly why it would go unnoticed if lost.

`_rounds()` holds no resource of its own (`src` is owned by the caller's
`maybe_aclosing`), so a caller breaking out of the `async for` needs no
`aclosing()` around it.

**Rejected: a `_grow(size)` one-liner** shared by all three ramp sites. That
*is* the thin-helper shape — a function whose body is shorter than its call —
and it would leave the reasoning stranded in a docstring away from either loop.

**Accepted residue:** `_fork_join_unordered_batches()` is a sliding window, not
a round loop, so it cannot use `_rounds()` and keeps its own
`size = min(size * 8, BATCH_SIZE)` line. Two sites become one plus one, not
three become one. The remaining pointer comment is then honest — it points at a
single definition rather than at "one of the other two".

### 5. `_run_round` and `_run_partition_round` stay two functions

They are the same body over a different `to_thread` callable, so parameterizing
by callable is the obvious collapse. It is not taken: once decision 3 lands,
each is a two-line function whose whole content is *which* worker runs and
*what* comes back (`list[list[Any]]` of elements versus
`list[TerminalSink]` of peers). A `_run_round(chain, batches, state_map, runner,
*extra)` signature would erase two clear names and two clear return types to
save two lines, and `*extra` exists only because the partition runner takes
`head`. Two named two-liners read better than one parameterized four-liner.

### 6. The state-map build goes to `fork_join.py` as `_shared_state(chain)`

Written twice today (`_fork_join_partitioned`, `_fork_join_batches`), five
lines each. It is fork/join's alone — the sequential path never builds one,
passing `{}` — so it belongs in `fork_join.py`, private, not in `pipeline.py`
next to the sinks it keys.

### 7. `WORKERS` moves to `fork_join.py` and stays bare

It is fork/join's number, and its long comment (the `PROCESSES` rename, the
process-pool design that was never built) is fork/join history.
`execution.py` imports it to bind `FORK_JOIN = _ForkJoin(WORKERS)` at import
time, so it stays bare under the naming rule. `decisions.md`
(`name-by-visibility-not-underscore`) removed it from the public export surface
and explicitly preserved `snakestream.execution.PROCESSES`'s successor as an
importable-for-information name; that migration note said the constant "keeps
its name and its value in `snakestream.execution`". Moving the module it lives
in is a second, smaller version of the same break, for a name no spec requires
to be importable and that `README` never shows in an import. Worth a line in
the change's own decisions entry when it closes; not worth a Migration entry.

### 8. `skip_specs: true`, and the spec prose corrected in place

Four SHALL statements cite `_wrap_sink()` by its underscored name
(`pipeline-composition` :3, :8, :231; `stream-iterator` :25) and the rename in
decision 1 makes that text stale. **Settled 2026-09-10: no delta, and the
identifiers are corrected in place as task 6.1.**

The rule this follows is `extract-unseeded-fold-module`'s: specs describe
behaviour, so if behaviour does not change, no spec should change either. A
delta here would produce a MODIFIED-Requirements block restating four
requirements verbatim but for one token, which is ceremony that obscures rather
than records — and `openspec validate` explicitly warns against inventing a
requirement to satisfy it.

**Editing `openspec/specs/**/spec.md` outside the delta flow is the unusual
half of this, and is deliberate.** The delta mechanism exists to change what a
spec *requires*; nothing here does. What task 6.1 changes is the same class of
thing as the comment sweep in task 6.2 — prose naming a function by a spelling
that no longer exists — and it is scoped to exactly that: the token
`_wrap_sink()` becomes `wrap_sink()`, and the two Purpose/SHALL sentences that
name it gain its new module where they already name a location. No SHALL is
added, removed, reordered or reworded otherwise. Anything beyond that scope
would mean a requirement really is changing, and would need its own delta and
its own change.

## Risks / Trade-offs

**A large mechanical diff hides a real edit.** → The five collapses are the
only semantic content; everything else must be a pure move. Land the move
first, verified by `git diff --stat` showing insertions matching deletions and
by a green suite, then the collapses as separate commits. That also makes the
one behaviour-preserving subtlety (decision 4's pre-pull guard) reviewable on
its own.

**The monkeypatch target is a string.** →
`tests/test_racing_encounter_order.py:473` patches
`"snakestream.execution._pull_round"`, which after the move resolves to
nothing and fails at *run* time, not import time. Grepping imports will not
find it. The suite must actually run; `-k pull_round` is not enough, since a
patch that silently no-ops can leave a test passing for the wrong reason —
check that the spy still records calls.

**Coverage gate.** → 98% is enforced on the GIL-enabled leg. Two pragma'd
unreachable branches move with their code (`_fork_join_partitioned`'s two
cancellation checks); decision 4's explicit pre-loop guard must keep its
`# pragma: no branch` or the gate will report a new partial branch.

**No benchmark gate, and that is a claim rather than an omission.** → Every
rejected cleanup in `decisions.md` (`add-callsite-dispatch`, the `merge()`
generator, routing `reduce()` through `reducing()`, `to_generator`) died on the
same measurement: a Python-level frame added to a *per-element* path. Nothing
here is on one. `_rounds()` yields once per round — once per up-to-`WORKERS`
OS-thread dispatches — and `_shared_state()` and `gather_or_cancel()` run once
per composition and once per round respectively. A module split moves
definitions and changes nothing at call time. A confirmation run of the
existing fork/join benchmark is still cheap insurance and should be recorded in
the closing entry, but no task is gated on a figure.

**Free-threaded leg.** → CI runs both `3.14` and `3.14t`. Nothing here touches
threading, but the fork/join machinery is where the two legs diverge, so both
must be green before this is called done.

## Migration Plan

Callers: nothing. No name in this change is re-exported from
`snakestream/__init__.py`; `stream.py`'s imports are unchanged by design
(Non-Goals). No `README` Migration entry — the same deliberate absence
`extract-racing-task-lifecycle` recorded, on the same grounds.

Implementation order, each step green before the next:

1. `pipeline.py` — move the seven primitives, drop their underscores, update
   `execution.py`'s imports and `tests/test_sequential.py` +
   `tests/test_name_visibility.py`.
2. `fork_join.py` — move the eleven fork/join definitions plus `WORKERS`,
   drop the underscore on `fork_join_through`/`fork_join_partitioned`, update
   `execution.py` and `tests/test_racing_encounter_order.py` (imports **and**
   the patch string).
3. Rewrite the three module docstrings so each describes only its own module.
4. The collapses, as separate commits: `gather_or_cancel`, `_rounds`
   (carrying the pre-pull guard), `_shared_state`.
5. Verify both CI legs, the gates and the coverage pragmas (tasks.md — 5).
6. Sweep the stale prose: the four spec statements citing `_wrap_sink()`
   (decision 8), then `stream.py:99`/`:113`, `sink.py:218`,
   `tests/test_fork_join.py`, `tests/test_close.py`, `tests/test_sink.py` —
   comments naming these functions with underscores and old modules.

Rollback is a revert; there is no data, no persisted state, and no public
surface involved.

## Open Questions

None. The one open question this design carried — whether the two specs citing
`_wrap_sink()` take a delta or the change takes `skip_specs: true` — was put to
the user and answered on 2026-09-10: `skip_specs: true`, with the spec prose
corrected in place as a task. Recorded as decision 8 above.
