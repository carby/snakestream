## Why

Execution mode is encoded as a **type**. `_derive()`'s `type(self)` is what
carries "am I parallel?" through a chain, so answering "how does this terminal
execute?" means knowing that `count()` calls `_drive_to()`, that `_drive_to()`
is virtual, that `ParallelStream` overrides it, and that its override reaches
back through `_compose()` into `_parallel()`. Three drive names
(`_drive`, `_drive_to`, `_drive_to_sequential`) and two dispatch seams
(`_compose`, `_drive_to`) sit across two axes that never read as a pair.

Two findings sharpened this while exploring:

**One name carries two unrelated meanings.** `_drive_to_sequential()` is both
the *measured fused fast path* (performance) and *"force encounter order, ignore
the stream's mode"* (semantics, used by `for_each_ordered` and by
`ParallelStream.find_first`). They share an implementation by coincidence.
Reading `ParallelStream.find_first() -> _drive_to_sequential()` gives no way to
tell which of the two is meant. It is the latter.

**`.parallel()` is position-dependent, and Java's is not.** Because
`_handoff()` composes the chain-so-far into a generator, ops declared *before*
the switch are frozen under the old mode. Java's `AbstractPipeline.parallel()`
is `sourceStage.parallel = true; return this;` — a flag on the source stage, so
the whole pipeline is affected regardless of where the call appears. Measured
here, 8 elements through a 100 ms async mapper:

| | wall clock | what actually ran raced |
|---|---|---|
| `.parallel().map(slow)` | **0.20s** | the map |
| `.map(slow).parallel()` | **0.81s** | nothing |
| `.map(slow)` (sequential) | 0.81s | — |

Same result, 4x the wall clock, no error. With 1:1 public API parity as this
project's first priority, that is an API-visible divergence, not an internals
detail — and fixing it is what removes the handoff, which is what removes an
entire generator layer.

## What Changes

- **Execution mode becomes a value.** `Stream` gains an `_executor` field
  holding `SEQUENTIAL` or `Racing(PROCESSES)`. **`ParallelStream` is deleted.**
- **One dispatch point.** `_drive_to()` and `_drive_to_sequential()` as
  dispatching names go away. Terminals call `self._evaluate(terminal)`, whose
  entire body is `return await self._executor.value(self._chain, self._stream,
  terminal)`. `_compose()` becomes the same one-liner over
  `self._executor.elements(...)`.
- **The default/override points the right way.** `Executor.value()`'s generic
  default is `drain(self.elements(...), terminal)`, which `Racing` simply
  inherits. `Sequential.value()` overrides it with the fused push — as a
  *documented, measured* fast path rather than as the base case. Today the base
  is the narrow sequential-only form and the subclass supplies the general one.
- **Forced-ordered execution becomes visible at the call site.**
  `for_each_ordered()` and the ordered branch of `find_first()` call
  `SEQUENTIAL.value(...)` explicitly, instead of relying on a never-override
  promise held in a docstring. `find_first` stops needing two implementations.
- **BREAKING** — **`.parallel()` / `.sequential()` become position-independent**,
  matching Java. They stop composing the chain-so-far into a generator and
  hand-ing it to a new stream; they return a new stream carrying the same source
  and the same chain under a different executor. Ops declared before the switch
  now run under the new mode. There is no longer such a thing as a mid-chain
  mode switch: the executor in force when a terminal runs governs the whole
  pipeline.
- **Falls out of the above, at no extra cost:** the empty-chain generator layer
  the handoff created disappears (five async-generator frames per element drop
  to four for `.parallel().map(f).count()`); the `stream.py` <-> 
  `parallel_stream.py` import cycle and its two function-local import
  workarounds go; `_handoff()`'s `cls` parameter goes; `PROCESSES` moves out of
  `stream.py`; and the live subclass-identity bug is fixed — `.parallel()` and
  `.sequential()` currently discard a `class MyStream(Stream)` subclass and its
  attributes, even though CLAUDE.md documents subclassing as supported.

Non-goals: no change to the racing execution model itself (partitioning,
spliterators and combiner wiring stay parked in **Later** — see design.md for
why racing is being kept deliberately rather than by omission); no change to any
public method name or signature; `Collector.combiner` stays accepted-and-never-
invoked; no third (multiprocess) executor.

## Capabilities

### New Capabilities

- `stream-execution-model`: the executor value itself — what an executor is,
  the two-method protocol, which executor a stream carries, how a terminal
  selects one, and the rule that a terminal needing encounter order names its
  executor explicitly rather than depending on the stream's.

### Modified Capabilities

Twelve capabilities name `ParallelStream`, `_drive_to*`, or racing in normative
requirement text. Most are mechanical renames of a class that ceases to exist;
four carry real behavioural change and are marked.

- `pipeline-composition`: **behavioural** — `_compose()`/`_parallel()` become
  executor methods, and position-independence means ops declared before a
  `.parallel()` now compose into the race. The per-composition shared-state
  guarantees (`distinct`, `limit`) hold unchanged but now apply to strictly more
  chains.
- `pipeline-immutability`: **behavioural** — mode switches must still return a
  new instance and invalidate the receiver, but they no longer compose. This is
  where the "must not be `self._executor = X; return self`" rule is pinned.
- `stream-find-first`: **behavioural** — the two `ParallelStream.find_first()`
  requirements collapse into one `Stream.find_first()` that reads the ordering
  flag and names `SEQUENTIAL` explicitly.
- `stream-ordering`: **behavioural** — the ordering flag survives a mode switch
  that no longer constructs a differently-typed instance.
- `terminal-sinks`: the three drive paths, restated over the executor protocol.
- `stream-foreach-ordered`: forced-ordered drive named explicitly.
- `stream-iterator`: "identical for sequential and parallel" restated without
  the two classes.
- `stream-close-handling`: handlers propagate across a mode switch that no
  longer composes.
- `stream-to-array`: "available on both `Stream` and `ParallelStream` with no
  subclass-specific override" — there is no subclass.
- `generic-stream-typing`: `ParallelStream[T]` no longer exists to parameterize.
- `mutable-reduction-collect`: the never-invoked `combiner` rationale, restated
  without naming the class.
- `callable-dispatch`: the per-composition classification scenario that names a
  `ParallelStream` composition fanning out.

## Impact

- **New** `src/snakestream/execution.py` — the executor protocol, `SEQUENTIAL`,
  `Racing`, `PROCESSES`, and the execution primitives as free functions.
- **Deleted** `src/snakestream/parallel_stream.py`.
- `base_stream.py` — `_drive`/`_drive_to`/`_drive_to_sequential`/`_compose`/
  `_handoff` restructured; `_executor` field; `sequential()`/`parallel()`.
- `stream.py` — terminals call `_evaluate`; `find_first` unified; `PROCESSES`
  and the `_concat` composition move or re-point.
- Tests: the suite has **51** `.parallel()` call sites. **Zero** have an
  intermediate op before `.parallel()` on the same line, so the single-line
  majority is unaffected. Four multi-line chains change what runs raced
  (`test_close.py:45`, `test_close.py:68`, `test_sequential.py:46`,
  `test_parallel.py:158`); their assertions are order-independent and should
  still pass. Two of those test a *concept that is being retired* — a mid-chain
  mode switch — and need rewriting rather than fixing. `test_compose.py` calls
  `stream._compose()`, which survives as a delegation; `test_sequential.py`
  imports `_wrap_sink`, unaffected.
- Docs: README migration-log entry for the `.parallel()` semantics change;
  CLAUDE.md's "Sequential vs. parallel execution" section is rewritten (it
  currently describes `ParallelStream` subclassing `Stream`); roadmap item moves
  from **Later** to **Done**.
