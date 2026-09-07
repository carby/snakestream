+++
id = "move-box-into-collectors"
title = "`Box` belongs with the collector containers"
bucket = "now"
rank = 1
filed = 2026-09-03
updated = 2026-09-06

[refs]
changes = ["move-box-into-collectors", "extract-encounter-order-model"]
specs = ["internal-name-visibility"]
files = ["src/snakestream/sink.py", "src/snakestream/collectors.py"]
+++

Split from [`sink-sentinel-placement`](sink-sentinel-placement.md) (filed
2026-09-03) on 2026-09-06. Scaffolded as the change of the same name — proposal
and design written, tasks not, specs deliberately skipped since no spec names
`Box`. Still queue work: nothing is implemented.

*Why it separated.* That item asked whether `UNSET`, `unseeded()` and `Box`
earn a module of their own. Counting the callers shows they were never one
question — `UNSET` has three importing modules, `unseeded()` and `Box` have one
each — and `Box`'s home is decided by counting rather than by judgement.
`collectors.py` uses it, in `counting()` alone, across four lines, and already
holds nine private containers of exactly its shape (`_SumBox`, `_AvgBox`,
`_SummaryBox`, `_ExtremumBox`, `_ReduceBox`, `_ToMapBox`, `_GroupBox`,
`_MappingBox`, `_CollectAndThenBox`). `sink.py` does not use it at all.

The rename to `_Box` follows from the naming rule rather than being a second
decision, and `tests/test_name_visibility.py` already checks it.

*Carries three stale comments with it.* `terminals.py`'s `CountSink` ("A plain
int, not a `Box`") and `ops.py`'s limit/skip state ("Kept out of `Box`
(`sink.py`)") both name the current address to explain a deliberate non-use, and
both are load-bearing rather than decorative. `sink.py`'s `UNSET` comment is
corrected only where it is wrong about `Box`; the rest of that sentence belongs
to the item this split from.
