+++
id = "split-comparator-out-of-sort"
title = "`comparator.py` split out of `sort.py`"
filed = 2026-08-25
closed = 2026-08-25
outcome = "shipped"
+++

**`comparator.py` split out of `sort.py`** (2026-08-25). Story 5 of the
2026-08-25 batch, and the last of the dependency chain. (Story 6, which
nothing waited on, landed after it and closed the batch.)

`sort.py` was named for one of the three things it held.
`check_comparator_result_type` and `is_new_extremum` are comparator
*semantics*, and their consumers — `_MinMaxSink` in `terminals.py`,
`min_by`/`max_by` in `collector.py` — sort nothing, yet both imported them
from a module called `sort`. That misdirection was the whole defect.

**Two modules, not one, and that was the user's call.** The roadmap row's
literal reading was to fold everything into one `comparator.py`, defensible
since `comparator-contract` governs all five functions. Rejected because it
renames around the defect rather than fixing it: one big `comparator.py`
would leave `ops.py` importing a *sort dispatcher* from a module named
`comparator` — the same misdirection pointed the other way. Split, each
importer gets a module whose name is accurate for what it takes from it, and
the already one-way dependency (sorting calls semantics; never the reverse)
becomes a visible import edge instead of an implicit file ordering.

**The row's open question — where `sort()` lands — was answered `sort.py`,
on the rule that the seam belongs with the caller, not the definer.**
`sort()` consumes comparator semantics exactly as `_checked` and `_merge` do.
Putting it in `comparator.py` would have left that module owning a function
whose only caller is `ops.py`, and `sort.py` reduced to `_checked` plus
`merge_sort` with no entry point — a module nothing imports directly. The
confirmation is `ops.py:15`: `from snakestream.sort import sort` reads
correctly before and after, unchanged, and `_SortedSink.end()`'s comment
naming `sort.py` stayed true. The decision that required no edit at the only
external call site is the one that matched what was already there.

**Beyond the story as written: `type.py` gained an alias, and `ty` is what
forced it.** The plan said to annotate `merge_sort`/`_merge` with the
`Comparator` union, reasoning it was a safe supertype and that adding a
narrowed alias was a different story. That was wrong on a checkable fact.
`Comparator` is `Callable[[T, T], int | Awaitable[int]]` and `_merge` awaits
it unconditionally, so annotating turned the await into
`invalid-await: int | Awaitable[int] is not awaitable`. The union is not a
safe supertype where the body does something only the narrow arm supports.
While the functions were bare, `ty` inferred nothing and said nothing —
**annotating is what surfaced it**, which is the argument for closing out
unannotated code rather than leaving it. Nothing else in the codebase hit
this because every other comparator await goes through
`_maybe_await`/`AsyncDispatch`, which return `Any`; `_merge` is the only site
awaiting a `Comparator` directly. Resolved with one line in `type.py` —
`AsyncComparator = Callable[[T, T], Awaitable[int]]` — and
`cast("AsyncComparator", comparator)` at `sort()`'s two reroute sites, where
`is_async_callable` or the trial comparison has just *proved* the narrowing.
A `cast("Awaitable[int]", ...)` inside `_merge`'s loop was rejected: it
states the narrowing at the least informative point and puts a cast on the
per-comparison path. Flagged and user-approved rather than absorbed.

**The annotation strand was an assumption, and it is worth recording as
one.** The roadmap row named the module's bare functions, so the work was
taken into scope without being confirmed. It paid for itself by finding the
`Comparator` gap, but the precedent is the assumption, not the luck. `src/`
now has **no unannotated function at all** (verified by `ast`, not grep).

**A pure move, and the instruments say so.** 562 tests green with **no test
file modified**, and coverage back at exactly **98.05%** — a move cannot
shift coverage, so an unchanged number is the evidence nothing else happened.
The `sort.py` diff is three hunks: one added import, the two removed
functions, and one docstring phrase (`_checked`'s "the same trick
is_new_extremum uses *above*", which the split falsified). `ruff`,
`ruff format --check`, `ty check src` and `openspec validate --strict` all
pass, plus a clean-interpreter `import snakestream` to rule out a cycle
between the two new modules. No spec impact — `skip_specs: true`; every
moved function kept its name, signature and body. See
`openspec/changes/split-sort-into-comparator-and-sort`.
