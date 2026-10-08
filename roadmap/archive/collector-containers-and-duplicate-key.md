+++
id = "collector-containers-and-duplicate-key"
title = "Collector containers, and the duplicate-key exception"
filed = 2026-08-25
closed = 2026-08-25
outcome = "shipped"
+++

**Collector containers, and the duplicate-key exception** (2026-08-25).
Story 6 of the 2026-08-25 batch — independent of the other five, and the one
that closed the batch. Three unrelated defects that shared a neighbourhood.

**(a) Nine hand-written containers became `@dataclass(slots=True)`.**
`_SumBox`, `_AvgBox`, `_SummaryBox`, `_ExtremumBox`, `_ReduceBox`,
`_ToMapBox`, `_GroupBox`, `_MappingBox`, `_CollectAndThenBox` each declared a
`__slots__` tuple and then wrote the same field list again in an `__init__`.
`slots=True` emits the same descriptors, so this is not the rejected
`CallSite` proposal wearing a new hat: those containers are built once per
collection by a collector's `_supply()`, never per element, and attribute
access inside `_accumulate` is unchanged. **Verified rather than asserted** —
a before/after harness compared slot names, constructed values and the
absence of `__dict__` across all nine and found them identical.

**The "~90 lines of boilerplate" the roadmap row claimed is not the number.**
The real saving is **-34 lines** (`collector.py` -25, `sink.py` -9). The ~90
counted the gross volume of `__slots__` tuples plus `__init__` bodies, but
the dataclass field declarations that replace them occupy most of that space
— a field is still a line. Only `_ToMapBox` is a large win (-10), because its
seven-field `__slots__` tuple was formatted across nine lines. The other
eight are -2 each. Legibility, not line count, is what this part bought:
the field list is now stated once.

**One field order had to change.** `_SummaryBox` took `seed` positionally but
declared `count` first, and a required dataclass field cannot follow
defaulted ones, so `total` moved to the front. Its single construction site
is `_SummaryBox(seed)`, so it still binds correctly — but it is a real
reordering, not a transcription, and it is the one place where the "change
nothing but the boilerplate" goal bent.

**(b) `Counter` is deleted, not renamed.** It shadowed `collections.Counter`
and added exactly one thing to `Box`: a default of `0`. Deleting it was the
user's call over a rename. The two `ops.py` `make_shared_state()` bodies
return `Box(0)`, and `counting()` — which had been passing the class object
itself as the supplier, `Collector(Counter, ...)`, relying on that default —
became `Collector(lambda: Box(0), ...)`. `partial(Box, 0)` was rejected as a
`functools` import for one call site.

**(c) `to_map` raises `IllegalStateException`, and it stays a `ValueError`
break.** Java's `Collectors.toMap` throws `IllegalStateException` on a
duplicate key, and this project already defines that class and already raises
it for pipeline reuse. The tempting softener — deriving `IllegalStateException`
from `ValueError` so existing `except ValueError` sites keep working — was
**rejected, and the reason is the other raise site**: the same class is what a
reused-stream error raises, and a stream-reuse error is not a `ValueError`
under any reading. Softening the break here would have mis-typed it there.
Loud for `except ValueError`, invisible to a bare `except`; spec delta on
`collector-to-map` and a README migration-log entry.

**The historical migration-log entry was deliberately left wrong.** README's
`redesign-collector-shape` entry illustrates interleaved downstream side
effects with "e.g. `to_map`'s duplicate-key `ValueError`". That was true at
that release. The log is read chronologically, so editing it would falsify
history; the new entry states the current type and the old one keeps its own.

**The tripwire held, with one honest exception.** 562 tests green,
`git diff --stat -- tests/` naming exactly the two files the row predicted.
But the row listed five `Counter` sites in `test_sink.py` and there were
**six** — a nested `_CountingStatefulOp` at lines 371-372 that the read
missed. It is in a named file and the import would not have resolved without
it, so it was converted rather than escalated. The lesson is about the
enumeration, not the tripwire: a grep would have found it and the row was
built from a read.

**Coverage went 98.05% -> 98.03%, and that is arithmetic, not a regression.**
The task list said to treat a drop as a lost test, so it was investigated:
missed statements (2), branches (288) and partial branches (26) are identical
before and after, and the uncovered set is the same two lines in
`_summarizing`. Total statements fell 1147 -> 1136 because the change deletes
eleven *covered* statements, which raises the weight of a fixed uncovered
remainder. **A pure-deletion change can lower a coverage percentage without
uncovering anything** — worth remembering the next time this gate moves.

`ruff`, `ruff format --check`, `ty check src` and
`openspec validate --strict` all pass, plus a clean-interpreter
`import snakestream` to rule out a cycle from `collector.py`'s new
`exception` import. See `openspec/changes/tidy-collector-containers`.
