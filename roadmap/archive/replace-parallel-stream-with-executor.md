+++
id = "replace-parallel-stream-with-executor"
title = "Replaced the `ParallelStream` subclass with execution mode as a value"
filed = 2026-08-21
closed = 2026-08-21
outcome = "shipped"
+++

**Replaced the `Stream` -> `ParallelStream` subclass with execution mode as a
value, and made `.parallel()`/`.sequential()` position-independent.** These
landed together because they are mechanically the same edit: the
compose-and-handoff is what carried mode as a type *and* what made the
switches positional.

**The exploration changed the shape of the item before it was proposed.** It
had been framed as an internals cleanup — inverted default/override, two
dispatch seams, an import cycle. Tracing `.parallel().map(f).count()`
end-to-end surfaced two things the entry had not:

*One name carried two meanings.* `_drive_to_sequential()` was both the fused
fast path (performance) and "force encounter order, ignore the stream's mode"
(semantics, used by `for_each_ordered` and `ParallelStream.find_first`). They
shared an implementation by coincidence, so reading
`ParallelStream.find_first() -> _drive_to_sequential()` gave no way to tell
which was meant. They are now separate: the fast path is an implementation
detail of `Sequential`, and forcing order is `SEQUENTIAL.value(...)` written
at the call site.

*`.parallel()` was position-dependent and Java's is not.* Because `_handoff()`
composed the chain-so-far into a generator, ops declared before the switch
were frozen under the old mode. Measured, 8 elements through a 100 ms async
mapper: `.parallel().map(slow)` took 0.20s, `.map(slow).parallel()` took
0.81s — identical to fully sequential. Java's `AbstractPipeline.parallel()` is
`sourceStage.parallel = true; return this;`, a flag on the source stage, so
the whole pipeline is affected wherever the call appears. With 1:1 public API
parity as this project's first priority, that made it an API divergence rather
than an internals detail. After the change both forms take 0.20s. **Note this
inverts the trap the old roadmap entry warned about** — it cautioned that
flipping a flag instead of handing off would "silently change semantics",
which is true, but the semantics it changes *to* are Java's. What survived
from that warning is the immutability half: the switch must still return a new
instance and consume the receiver, so it is `_derive_executor()`, never
`self._executor = X; return self`. **Superseded 2026-08-26 by
`collapse-derive-wrappers`:** `_derive_executor()` no longer exists.
`sequential()`/`parallel()` now derive with no op and assign `_executor`
themselves, and the immutability rule this entry states is unchanged — it
lives on `sequential()`'s docstring, at full length precisely because that
body is one line away from the forbidden in-place flip.

**Racing was kept deliberately, not by omission.** Partition-plus-combine
(spliterator splits, per-partition pipelines, a `combiner` merge) was explored
and set aside: Java's own answer for a non-splittable source
(`Spliterators.IteratorSpliterator.trySplit()`, which drains a growing batch
into an array) trades latency-to-first-element for throughput, which is the
wrong trade for an async/IO-first library where racing yields an element the
instant any branch produces one. The rule adopted: **Java is the public-API
contract, not the implementation blueprint.** Partitioning, `spliterator()`
and combiner wiring stay in **Later**.

**The one asymmetry in the new protocol is there on measurement.**
`Executor.value()`'s generic default is `drain(elements(...), terminal)`,
which `Racing` inherits unchanged; `Sequential.value()` overrides it with the
fused push. The task list put a gate before the design was allowed to keep
that override, and it came back far larger than the +10-50% band the
flush-dedup measurements had set as the expectation (Python 3.14.5, 20,000
elements, no intermediate chain, best of 5, ns/element):

| Variant | Fused | Generic | Delta |
|---|---|---|---|
| `count()` | 303 / 296 / 320 | 669 / 664 / 745 | **+125%** |
| `reduce(acc)` sync | 353 / 351 / 348 | 745 / 739 / 775 | **+112%** |

More than twice the cost per element, because this removes the async-generator
round trip entirely rather than adding one object to a loop that already had
one. The override stays and carries these figures in its docstring.

**What went away:** `ParallelStream` and `parallel_stream.py`; `_drive`,
`_drive_to`, `_drive_to_sequential`, `_parallel` and `_handoff`; both dispatch
seams, replaced by `_compose()` and `_evaluate()`, one line each; the
`stream.py` <-> `parallel_stream.py` import cycle and its two function-local
import workarounds; `ParallelStream.find_first()`, unified into one
implementation selecting on the ordering flag; and one generator layer per
element on parallel pipelines, since a mode switch no longer composes
(`.parallel().map(f).count()` went from five async-generator frames to four).
**What arrived:** `execution.py` with four primitives, two executors and
`PROCESSES`. It also **fixed a live bug**: `.parallel()`/`.sequential()` were
the only ops in the library that discarded a `Stream` subclass and its
attributes, despite CLAUDE.md documenting subclassing as supported.

**The "green with no test edited" tripwire could not apply** — the behaviour
change is the point — so it was replaced with a diff check: only the test
sites identified *before* any source edit were allowed to differ. The
pre-analysis found 51 `.parallel()` sites across 17 files, zero with an op
before `.parallel()` on the same line, and four multi-line chains that change
what runs raced. All four assertions were predicted to survive, and did; the
two in `test_close.py` passed untouched. The two in `test_sequential.py` and
`test_parallel.py` were rewritten rather than patched, because they tested
mid-chain mode switching — a concept this change retires — and their names
were already inverted relative to what they did. They now assert the new rule
by timing, the same measurement that found the divergence. 535 tests green,
coverage 98.08%. One new capability (`stream-execution-model`) and 11 spec
deltas. See `openspec/changes/replace-parallel-stream-with-executor`.

**Two decisions resolved along the way, recorded so they are not re-opened.**
`Racing` holds `workers` as a field, which makes a public `.parallel(n)`
trivially available — **deliberately not exposed**, because Java has no such
overload and 1:1 surface parity is the first priority. Tune `PROCESSES`
instead. And `unordered()` **stays a stream flag rather than moving onto the
executor**: the executor answers *how* a pipeline runs, the flag answers
*whether the caller requires encounter order*. Folding the flag in would mean
`Racing` needed ordered and unordered variants, which is how `find_first()`
ends up with two implementations again — the exact thing this change removed.

**Left open deliberately:** whether `BaseStream` should collapse into `Stream`
now that `ParallelStream` is gone. Java has `BaseStream` because
`IntStream`/`LongStream`/`DoubleStream` share a parent; this library has no
primitive specializations and already collapsed that distinction, so the split
may be organizing nothing. It roughly doubles the diff and is independently
revertable, so it is a follow-up rather than part of this change.
