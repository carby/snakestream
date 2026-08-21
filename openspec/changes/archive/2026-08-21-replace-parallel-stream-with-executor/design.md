## Context

See `proposal.md` — Why. What shapes the approach:

- **Racing is being kept on purpose.** Exploration considered replacing it with
  Java's partition-plus-combine (spliterator splits, per-partition pipelines,
  `combiner` merge) and rejected that for now: Java's model is
  collection/CPU-first, and its answer for a non-splittable source
  (`Spliterators.IteratorSpliterator.trySplit()`, which drains a growing batch
  into an array) trades latency-to-first-element for throughput. This library is
  async/IO-first, where racing yields an element the instant any branch produces
  one. The rule adopted for this change: **Java is the public-API contract, not
  the implementation blueprint.** Partitioning stays in **Later**.
- **The fused sequential path is measured, not cosmetic.** The
  `collapse-terminal-drive-loop` change established that `_copy_into()`, entered
  once per stream, is free, while per-element helpers on that path cost +10%
  (sync closure) to +50% (async closure). `_drive_to_sequential()`'s fusion
  removes a `GeneratorBridgeSink` accept, a buffer append, a buffer check and a
  generator `yield` **per element**. It is in the expensive band. It survives —
  as an override with a number attached.
- **`ParallelStream` is invisible from outside.** Not exported (`__init__.py`
  exports only `Stream`), zero `isinstance` checks, no test imports it.

## Goals / Non-Goals

**Goals:**
- One greppable answer to "how does this terminal execute?"
- Each execution primitive has exactly one meaning.
- The general implementation is the base; the specialisation is the override.
- `.parallel()`/`.sequential()` behave as Java's do.

**Non-Goals:**
- Changing the racing algorithm, `PROCESSES`, or `_guarded()`'s lock discipline.
- Wiring `Collector.combiner` or `reduce`'s combiner — they stay parity-only.
- A third executor. This change makes one *possible*; it does not add one.
- Collapsing `BaseStream` into `Stream`. See Open Questions.
- Renaming any public method.

## Decisions

### 1. Two executor methods, mirroring the two things a pipeline can produce

```
elements(chain, source) -> AsyncGenerator      lazy, pull, for iterator()/to_generator()
value(chain, source, terminal) -> Any          eager, push, for every other terminal
```

Backed by free functions with no `self` — which is what they already are today
in all but syntax (`_drive()` references `self` **not at all**; `_parallel()`
references it **only** to reach `self._drive`, i.e. only to reach the other
strategy):

```
stream_through(chain, src)        -> AsyncGen    was _drive
race_through(chain, src, workers) -> AsyncGen    was _parallel
feed_through(chain, src, terminal)-> value       was _drive_to_sequential (fused)
drain(gen, terminal)              -> value       was _copy_into + .result()

class Executor:
    def elements(...): ...                        # abstract
    async def value(self, chain, src, terminal):  # GENERIC DEFAULT
        return await drain(self.elements(chain, src), terminal)

SEQUENTIAL:  elements = stream_through
             value    = feed_through   # override — measured fast path
Racing(n):   elements = race_through
             value    = inherited      # the general form
```

Rejected: keeping `_drive_to()` as a virtual method on the stream and only
moving `_compose()`. That leaves two dispatch seams, which is half the
comprehension problem.

Rejected: eliminating `feed_through` for a symmetric one-primitive protocol.
That is the "don't cosplay symmetry" case — it routes every sequential
`count()`/`reduce()`/`collect()` through a generator layer. Task 1 measured it
rather than assuming the inherited +10–50% band, and the answer is much larger
than that band (Python 3.14.5, 20,000 elements, no intermediate chain, best of
5, three independent invocations, ns/element):

| Variant | Fused | Generic compose-then-drain | Delta |
|---|---|---|---|
| `count()` | 303 / 296 / 320 | 669 / 664 / 745 | **+125%** |
| `reduce(acc)` sync | 353 / 351 / 348 | 745 / 739 / 775 | **+112%** |

The generic form is **more than twice** the cost per element. That is not a
tidiness-versus-speed trade to weigh; it settles the decision outright. The
fused override stays, and `Sequential.value()` carries these figures in its
docstring so the next reader does not have to re-derive why the one asymmetry in
the protocol exists.

Worth noting *why* it is so much larger than the flush-dedup measurements that
set the +10–50% expectation: those added one object or one call per element to a
loop that was already generator-driven. This removes the generator entirely —
per element it saves a `GeneratorBridgeSink.accept()`, a buffer append, a
truthiness check, a `yield` (with its suspend/resume across the async-generator
boundary), and a list clear. The async-generator round trip dominates.

### 2. Forced-ordered execution is an argument, not a promise

`_drive_to_sequential()` today means two things. They separate:

| meaning | today | after |
|---|---|---|
| the fused fast path | `_drive_to_sequential` | `SEQUENTIAL.value()`, an implementation detail of one executor |
| force encounter order regardless of mode | `_drive_to_sequential`, protected by "never overridden" in a docstring | `SEQUENTIAL.value(...)` written at the call site |

`for_each_ordered()` and the ordered branch of `find_first()` name `SEQUENTIAL`
explicitly. `ParallelStream.find_first()` disappears: one `Stream.find_first()`
reads `is_ordered()` and either delegates to `find_any()` or drives under
`SEQUENTIAL`.

### 3. `.parallel()` / `.sequential()` — flag semantics, immutable form

This is the behavioural change, and it has one trap the type checker cannot
catch. The tempting form is wrong:

```python
def parallel(self):
    self._executor = RACING  # WRONG: mutates in place
    return self  # violates pipeline-immutability
```

The project shipped `pipeline-immutability`: every op returns a new instance and
marks the receiver consumed. The mode switch must keep doing that — it just
stops *composing*:

```python
def parallel(self):
    return self._derive_executor(RACING)  # new instance:
    #   same source, same chain,
    #   different executor,
    #   ordering flag + close handlers carried,
    #   subclass identity preserved via type(self),
    #   receiver marked consumed
```

Note the earlier roadmap entry flagged the *opposite* trap — that flipping a
flag "silently changes semantics" versus the compose-and-handoff. That reading
predates the measurement in the proposal: the compose-and-handoff **is** the
divergence from Java, so the semantics it protects are the ones being corrected.
What remains true from that warning is the immutability half, which is why
`_derive_executor` exists rather than an assignment.

Two consequences to state plainly:

- **A mid-chain mode switch stops being a concept.** `.parallel().map(f)
  .sequential().count()` runs entirely sequentially, because the executor in
  force at the terminal governs the whole pipeline. That is Java's behaviour.
- **Ops before a `.parallel()` now run raced**, including stateful ones. The
  shared-state machinery (`Op.make_shared_state()`, one state map per
  composition passed into every branch) already handles `distinct`/`limit`
  across branches and is specified and tested. This change routes strictly more
  chains through it; it introduces no new mechanism.

### 4. `unordered()` stays a stream flag, not an executor property

The executor answers *how* a pipeline runs. `_ordered` answers *whether the
caller cares about order*. `find_first` reads the flag to decide whether to
force `SEQUENTIAL`. Folding the flag into the executor would mean `Racing`
needed ordered and unordered variants, which is how `find_first` ends up with
two implementations again.

### 5. `PROCESSES` and module placement

Both primitives, both executors and `PROCESSES` live in a new
`src/snakestream/execution.py`. That is what dissolves the `stream.py` <->
`parallel_stream.py` cycle: `execution.py` imports from `sink.py` only, and
`base_stream.py`/`stream.py` import from it in one direction. `PROCESSES` keeps
its name and default of 4 (public, documented, Java-parity-adjacent) and simply
stops living in `stream.py`.

## Risks / Trade-offs

- **The "green with no test edited" tripwire dies.** Every previous structural
  change in this project used it. It cannot apply here: the behaviour change is
  the point. → Replacement tripwire, in two halves: (a) every test *not* in the
  four identified multi-line chains must pass untouched — a diff check, not a
  judgement call; (b) the four chains get explicit before/after reasoning in the
  task list, and the two testing a retired concept are rewritten deliberately,
  not patched until green.
- **A silent performance regression for callers who wrote `.map(f).parallel()`
  expecting sequential mapping.** → Impossible to hit *negatively*: that form
  gets faster, not slower. The genuine risk is the reverse — a caller who
  deliberately placed `.parallel()` late to keep an expensive op sequential now
  gets it raced. Migration-log entry must say this explicitly, since nothing
  raises.
- **Stateful ops on newly-raced paths.** → `distinct`/`limit`'s shared-state
  guarantees are already specified in `pipeline-composition` with scenarios;
  those scenarios must be re-pointed at chains where the op precedes the
  `.parallel()`, which is the newly-reachable case.
- **Twelve spec deltas is a large blast radius for one change.** → Eight are
  mechanical renames of a deleted class name; four carry behaviour. Splitting
  the mechanical ones into a follow-up was considered and rejected: they would
  describe a class that no longer exists in the interim, which is worse than a
  large diff.
- **`Sequential.value()` remains a performance-motivated specialisation inside
  an otherwise clean protocol.** → Accepted, and named as such in the code with
  its measurement. The alternative is paying per element for tidiness.

## Migration Plan

Pre-1.0 hard break, no deprecation window, matching `stream_of()` -> `Stream.of()`,
the `Stream.of()` kwargs removal, the `str`/`bytes` change, `Stream.concat` and
`to_list()`. A README migration-log entry states: `.parallel()` and
`.sequential()` now apply to the whole pipeline regardless of where they appear;
a caller who placed `.parallel()` after an op to keep that op sequential must
split the pipeline into two streams instead. **This one breaks silently** —
results are unchanged, only which ops run raced changes — so the entry must be
explicit that there is no exception to look for. Rollback is a revert of the
whole change; the executor refactor and the semantics change are one commit
because they are mechanically the same edit.

## Test-site analysis (tasks 2.1-2.3, done before any source edit)

Inventory: **51** `.parallel()` call sites and **7** `.sequential()` sites across
**17** test files. Every single-line usage is `Stream.of(...).parallel().<ops>`,
which is unaffected. The four multi-line chains where an op precedes a mode
switch, with what runs raced before and after:

| Site | Chain | Before | After | Assertion holds? |
|---|---|---|---|---|
| `test_close.py:44` `test_close_after_stream_switch` | `.map().on_close().distinct().parallel().on_close().collect()` | map + distinct sequential; race over an empty chain | map + distinct both raced; `distinct` uses its shared-state path | **Yes** — asserts only that both close handlers fired |
| `test_close.py:68` `test_close_after_sequential_switch` | `.map().on_close().parallel().distinct().sequential().on_close().collect()` | map sequential, distinct raced, then composed into a sequential collect | whole pipeline sequential; nothing raced | **Yes** — asserts only close handlers |
| `test_sequential.py:45` `test_sequential_switch_to_parallel` | `.parallel().map().sequential().distinct().collect()` | map raced, distinct sequential | whole pipeline sequential | **Yes** — asserts 4 distinct letters |
| `test_parallel.py:154` `test_sequential_switch_to_sequential` | `.sequential().map().parallel().distinct().collect()` | map sequential, distinct raced | map + distinct both raced | **Yes** — asserts 4 distinct letters |

**All four assertions survive**, so the suite passing is necessary but not
sufficient evidence. The last two are the ones testing a retired concept: their
whole point is that a mode switch applies from that point onward, which is
exactly what stops being true. Passing unchanged would mean they had stopped
testing anything.

Drafted replacements (task 2.2) — assert the new rule directly, by timing, since
that is the only externally observable difference:

- `test_sequential.py:45` becomes: a late `.sequential()` makes the **whole**
  pipeline sequential. `.parallel().map(slow).sequential().collect()` over N
  elements takes about `N x delay`, not `N/workers x delay` — proving the
  earlier `.parallel()` did not leave the map raced.
- `test_parallel.py:154` becomes: a late `.parallel()` makes the **whole**
  pipeline raced. `.sequential().map(slow).parallel().collect()` takes about
  `N/workers x delay` — proving the map declared before the switch ran raced.

Both mirror the probe in `proposal.md`, which is the same measurement that
found the divergence. Their names should change with them: the current names
(`switch_to_parallel` on a chain ending sequential, `switch_to_sequential` on a
chain ending parallel) are already inverted and would be actively misleading
under the new semantics.

## Open Questions

- **Does `BaseStream` survive?** Java has it because `IntStream`/`LongStream`/
  `DoubleStream` share a parent; this library has no primitive specialisations
  and already collapsed that distinction. With `ParallelStream` gone, the
  `BaseStream`/`Stream` split may be organising nothing. Deferred deliberately:
  it roughly doubles the diff and is independently revertable, so it is a
  follow-up change, not a task here.
- **Does `Racing` holding `workers` as a field open up `.parallel(n)`?**
  Probably a deliberate no — Java has no such overload, and API parity is the
  first priority. Worth recording as a decision rather than leaving implicit.
