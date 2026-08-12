## Context

`stream.py` already implements `limit(n)` via `_LimitOp`, a callable class with
`make_state()` (returns fresh per-call state) and `__call__(iterable,
state=None)` (falls back to `make_state()` when no external state is passed).
`ParallelStream._parallel()` (`parallel_stream.py:21-26`) generically detects
`make_state` on any queued closure and shares one state instance across all
racing branches of a composition, so `distinct()`/`limit()` already get
globally-correct parallel behavior for free — no `ParallelStream`-specific
code exists for either op. `skip(n)` is small enough to mirror `_LimitOp`
directly rather than requiring new architecture.

## Goals / Non-Goals

**Goals:**
- Add `Stream.skip(n)` as an intermediate op, dropping the first `n` elements.
- Fresh state per composition (matching `limit()`/`distinct()`), and
  globally-correct shared counting across `ParallelStream` branches.
- No upstream over-pulling beyond what's necessary to know a skipped element
  should be dropped (this op has to pull the skipped elements to consume them
  — unlike `limit()`, there's no short-circuit available, since the first `n`
  elements must be actually drained from upstream, not merely uncounted).

**Non-Goals:**
- No new short-circuit behavior — `skip()` cannot avoid pulling the first `n`
  elements, since it has to advance upstream past them.
- No change to `ParallelStream` internals; the existing `make_state()` wiring
  is reused unmodified.
- No revisiting of the mutable-builder-vs-immutable-pipeline question tracked
  separately in `roadmap.md`'s Next bucket.

## Decisions

- **Mirror `_LimitOp` as `_SkipOp`**: a callable class with
  `make_state() -> list[int]` (a 1-element mutable counter, matching
  `_LimitOp`'s pattern) and `async def __call__(iterable, state=None)` that
  drains and discards elements while `state[0] < self._n`, incrementing the
  counter per drained element, then yields everything after. Chosen over a
  plain closure so the same `make_state()`-detection in
  `ParallelStream._parallel()` picks it up automatically, requiring zero
  `parallel_stream.py` changes — same reasoning `_LimitOp`/`_DistinctOp`
  already established.
- **Parallel semantics**: with one shared counter across racing branches, the
  *first* `n` elements pulled by any branch (in whatever order branches race
  the upstream) are dropped, and the rest pass through — mirroring how shared
  `limit()` state already makes "first n" a global, not per-branch, guarantee
  under racing. Order is not guaranteed under `.parallel()` in general
  (documented for `ParallelStream` already), so "first n" here means "first
  n pulled," not "first n in source order."
- **No short-circuit optimization**: unlike `limit()`, which can stop pulling
  once its count is reached, `skip()` must pull and discard every one of the
  first `n` elements to advance past them — there's no way to "skip" a pull
  from an async generator without consuming it. This is inherent to the
  operation, not a missed optimization.

## Risks / Trade-offs

- [Parallel `skip(n)` drops "first n pulled," not "first n in source order,"
  since branches race independently] → Already true of `ParallelStream` in
  general (documented, not new); note it in the spec scenario so it's not
  mistaken for a bug.
- [Shared counter under parallel racing needs the same idempotency care
  `_LimitOp` needed for its shared `size_holder`] → Reuse the same
  list-based mutable-counter pattern already proven correct by
  `pipeline-composition`'s existing tests; no new concurrency primitive
  introduced.

## Migration Plan

Purely additive — no existing public API changes. No migration or rollback
steps beyond a normal merge.
