+++
id = "collapse-drive-loops-into-copy-into"
title = "Collapsed the two terminal drive loops into `_copy_into()`"
filed = 2026-08-20
closed = 2026-08-20
outcome = "shipped"
+++

**Collapsed the two terminal drive loops into `_copy_into()`.**
`BaseStream._drive_to_sequential()` and `ParallelStream._drive_to()` each
spelled out the same begin / cancellation-guard / accept-loop / end sequence;
both now call a module-level `_copy_into(head, src, state_map)` in
`base_stream.py`, named after Java's `AbstractPipeline.copyInto()` the way
`_wrap_sink()` is named after `wrapSink()`. The pre-first-pull guard's
reasoning — a chain can already be cancelled before it has seen anything
(`limit(0)`) — now has one home instead of being a comment in one of three
copies. `ParallelStream._drive_to()`'s `_maybe_aclosing` scope widened to
cover the whole drive, matching the sequential form; the only delta is
constructing (never starting) the composed generator on the already-cancelled
path, verified to start no task and leave nothing pending. Two source files,
+21/-19 lines, no test assertion changed (two stale comment references in
`tests/test_sink.py` were repointed at `_copy_into()`), coverage 98.15% ->
98.21%. **No README edit was needed**: every name involved — `_copy_into`,
`_drive`, `_drive_to`, `_drive_to_sequential`, `_maybe_aclosing`,
`_wrap_sink` — is private and unexported, and no parity table entry changes.

Folded in before archiving: `_compose()` gained the docstring it was missing.
It is the third member of the dispatching/overridden family alongside
`_drive_to` and `_drive_to_sequential` — the seam where execution mode is
decided, which `ParallelStream` overrides to fan the chain into a race — and
it was the only one not saying so, which made it read as a pointless
delegation to `_drive()`. `_drive()` cannot be that seam: `_parallel()` calls
it once per racing branch, so overriding it would make each branch fan out
again.
