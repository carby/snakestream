## Context

`BaseStream` (`base_stream.py`) is the shared root of `Stream` and
`ParallelStream` and already holds two pieces of instance state:
`self._stream` (the normalized source) and `self._chain` (queued
intermediate-op closures). `Stream`'s intermediate ops mutate `self` and
return it rather than building a new instance, and `sequential()`/
`parallel()` compose the current chain into a fresh source and hand it to a
new `Stream`/`ParallelStream`, resetting the chain. `unordered()` needs to
fit the same mutation model and survive that mode-switch reset.

There is currently no consumer of an "is this stream ordered" flag — `Stream`
always preserves encounter order and `ParallelStream` never does, regardless
of any flag. `unordered()` is being added now, ahead of its consumers
(`forEachOrdered()`, `find_first()`), purely to unblock their design per
`roadmap.md`'s Now #2/#3 ordering. This change intentionally does not
implement either consumer.

## Goals / Non-Goals

**Goals:**
- Track a per-instance "ordered" flag on `BaseStream`, defaulting to `True`.
- Provide `unordered()` (mutate flag, return `self`) and `is_ordered()`
  (query) matching the existing `is_parallel()` query convention.
- Propagate the flag when `sequential()`/`parallel()` construct a new
  instance, so declaring a pipeline unordered survives a mode switch — Java's
  `unordered()` is a permanent characteristic of the pipeline, not tied to
  sequential-vs-parallel execution.

**Non-Goals:**
- Implementing `forEachOrdered()` or `find_first()` — those are separate,
  later roadmap items that will *consume* this flag.
- Changing actual iteration order in `Stream` or `ParallelStream` — no
  execution-path behavior changes in this change.
- Any interaction with `distinct()`/`limit()`/`sorted()` state — those are
  unaffected by encounter-order bookkeeping.

## Decisions

- **Mutate-and-return-self, not a new instance.** Matches every other
  chainable method on `BaseStream`/`Stream` (`filter`, `map`, `on_close`,
  etc.) per the chain-of-closures model documented in `CLAUDE.md`. A
  new-instance approach would be inconsistent with the rest of the API and
  is explicitly out of scope per the still-open "mutable-builder vs.
  immutable-pipeline" decision tracked in `roadmap.md`'s Next section.
- **Flag lives on `BaseStream`, not `Stream`/`ParallelStream`.** Both
  subclasses need it (`ParallelStream` extends `Stream`), and `is_parallel()`
  already establishes the precedent of ordering/mode queries living on the
  base class.
- **`sequential()`/`parallel()` copy the flag onto the new instance.**
  Alternative considered: reset to `True` on every mode switch (mirroring how
  `self._chain` resets). Rejected because Java's `unordered()` is a
  pipeline-wide characteristic independent of sequential/parallel execution
  mode — resetting it on a mode switch would silently discard the caller's
  explicit declaration, which is a worse default than propagating it.
- **No propagation through `.on_close()`'s handler list or other unrelated
  state.** Only `_ordered` is copied; this stays a single boolean, not a
  broader "instance config" bag, to avoid speculative generality.

## Risks / Trade-offs

- [Flag has no observable effect yet, so a test can only assert the flag's
  own bookkeeping] → Acceptable: the same "infrastructure ahead of consumer"
  shape already exists in this codebase (e.g. `is_parallel()` existed before
  every caller that branches on it), and the roadmap explicitly sequences
  `unordered()` before its consumers.
- [Future `forEachOrdered()`/`find_first()` design could discover the flag
  needs different semantics than a plain instance boolean, e.g. needing to
  survive `.filter()`/`.map()` chaining mid-pipeline rather than only
  `.sequential()`/`.parallel()`] → Since intermediate ops already mutate and
  return the same `self`, the flag naturally survives chaining without extra
  work; only the mode-switch (new-instance) case needed an explicit decision,
  which this design makes.

## Migration Plan

Purely additive — no existing method signatures or behavior change. No
rollback concerns beyond reverting the added methods/state.
