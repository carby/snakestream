+++
id = "limit-short-circuit"
title = "Made `limit(n)` a real short-circuit"
filed = 2026-08-12
closed = 2026-08-12
outcome = "shipped"
+++

Made `limit(n)` a real short-circuit: `_LimitOp.__call__` (`stream.py`) pulled
an element from upstream *before* checking whether `max_size` had already
been reached, so every `limit(n)` pipeline pulled `n+1` elements instead of
`n` — e.g. `Stream.of([1,2,3,4,5]).peek(seen.append).limit(2)` returned
`[1, 2]` but left `seen == [1, 2, 3]`. Fixed by checking the size before
pulling rather than after, so upstream is closed without ever pulling an
`n+1`th element. Under `.parallel()`, the shared `size_holder` in
`ParallelStream._parallel`'s `state_map` already gave a global (not
per-branch) limit guarantee; the fix changes *when* the shared source gets
closed — whichever branch observes the shared count reaching `max_size`
closes it before pulling further — and closure was made idempotent so a
second racing branch closing (or pulling from) an already-closed shared
source doesn't raise out of the task loop. No public API change. See
`openspec/changes/archive/2026-08-12-fix-limit-short-circuit`.
