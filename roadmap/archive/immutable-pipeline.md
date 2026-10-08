+++
id = "immutable-pipeline"
title = "Decided and implemented the mutable-builder vs. immutable-pipeline question"
filed = 2026-08-18
closed = 2026-08-18
outcome = "shipped"
+++

Decided and implemented the mutable-builder vs. immutable-pipeline
question (the former top **Next**-bucket item, previously "Decide
mutable-builder vs. immutable-pipeline semantics"). Explored three
positions during a design session: (A) keep mutate-and-return-self and
just document the aliasing risk; (B) copy-on-write with the old
reference left silently usable (superficially "forkable," but still a
footgun since the underlying `self._stream` is single-pass, so both
forks would race it exactly like `ParallelStream` branches do); (C)
Java-exact — new instance plus invalidating the old reference on reuse.
Landed on a scoped version of (C): every intermediate op (`map`,
`filter`, `flat_map`, `sorted`, `distinct`, `peek`, `limit`, `skip`) and
both mode switches (`sequential()`, `parallel()`) now return a **new**
`Stream`/`ParallelStream` instance via a new `BaseStream._derive()`
helper (`base_stream.py`) instead of mutating and returning `self`;
using an already-superseded old reference for any further
pipeline-building or terminal call now raises a new
`IllegalStateException` (`exception.py`), checked via a
`self._consumed` flag set only by the ops that build a new instance.
Deliberately did **not** go full Java-exact: terminal ops
(`collect`, `reduce`, `for_each`, etc.) check `self._consumed` but never
set it, so repeating a terminal op on a reference that was never used to
build a further instance keeps today's exact behavior (an exhausted
source yields an empty result rather than raising) — reversing that
would have undone the already-shipped, tested `fix-stream-rerun-state`
contract that `pipeline-composition` documents, which was judged a
separate, already-settled decision this change shouldn't revisit.
`on_close()`/`close()` were kept completely exempt from the new check,
matching how Java itself tracks close handlers at the pipeline's source
stage rather than per operation, independent of any per-op immutability
question. Discovered during implementation: `BaseStream.__init__`'s
`self._close_handlers = close_handlers or []` treated an *empty* list as
falsy and silently created a new list instead of keeping the passed-in
reference — invisible before since intermediate ops never re-invoked the
constructor, but every op does now via `_derive()`, breaking
close-handler continuity across the very first op called before any
`on_close()`. Fixed to `[] if close_handlers is None else close_handlers`.
Added `tests/test_pipeline_immutability.py`: new-instance-per-op checks
and invalidation-raises checks for all 8 intermediate ops, invalidation
checks across all terminal ops and both mode switches, derived-instance
usability, the unextended-reference non-regression case, and the
`on_close()`/`close()` exemption. Added a new `pipeline-immutability`
spec. Updated README's migration log (**BREAKING**). See
`openspec/changes/make-stream-ops-immutable`.
