+++
id = "segment-sign-sharing-cost"
title = "Sharing anything between the segment-sign twins measures ~3%"
bucket = "now"
rank = 3
filed = 2026-09-08
gate = "a shape that de-duplicates without paying the ~3%, or a measurement on other hardware that overturns it - not a tidier version of the same call"

[refs]
specs = ["comparator-contract", "comparator-null-ordering"]
files = ["src/snakestream/comparator.py"]
+++

`_segment_sign_sync` and `_segment_sign_async` differ only in extraction, which
is the only part of a segment that can await. Everything else about them is
duplicated, and every attempt to share it has measured ~3% on an async,
null-tolerant chain.

**Half of it is already in the tree** (`b1f5db2`). Extraction is factored into
`_extract_pair_sync`/`_extract_pair_async`, collapsing four shapes into two and
replacing the `nulls is NullPlacement.ABSENT` two-arm split with one shared
`nulls is not ABSENT and (ea is None or eb is None)` guard. That commit is a
checkpoint: it carries the ~3% described below, deliberately and not yet
argued.

**What is still duplicated:** the six lines each twin ends with - the
`comparator is None` natural-ordering branch, the `type(sign) is not int`
contract check, and the return.

## The measurements

All on an async, null-tolerant chain (min of 200 comparisons over 2000 pairs,
order-balanced alternating rounds, WSL2). A **null test** - the baseline
benchmarked against a byte-identical copy of itself - separates by ~0.4%, which
is the noise floor these sit above.

| shape | cost | rounds |
|---|---|---|
| hoisting the null check out of the tolerant arm (**in the tree now**) | ~3.1% | 6/6 |
| sharing the six-line tail as `_compare_keys(ea, eb, comparator)` | ~3.3% | 6/6 |
| both together | ~3.9% | 8/8 |

Both cost about the same and they do not cleanly add, which is itself
unexplained and worth not over-reading. Sync chains and async intolerant chains
were unaffected in every run.

**Dead ends, already tried:** a per-operand `_passes_through()` predicate and
an inline-everything shape with no helpers at all. Both are called twice as
often as `_compare_keys` for less work, and neither beat the two-arm original.

## Why it is a real question and not a tidiness itch

The trade already has a precedent in this same file, on the same side:
`is_new_extremum`'s docstring records that delegating its contract check
"measured ~5%", which is why that check is written out at every call site
instead. If the answer here is the same, the deliverable is a comment
recording it - so the next reader stops where this one did - not a refactor.

The path is narrow: `KeyComparator.__call__` only, since `sorted()` takes the
decorate-sort-undecorate column instead, and only for chains that are both
async and null-tolerant.

## What the analysis corrected

The two-arm extraction shape was justified in both docstrings by the type
checker being unable to narrow through a compound `nulls is not ABSENT and
(...)` guard. **That reason never held** - the `cast("Any", ...)` those arms
already wrote leaves nothing to narrow. The shape was right and the argument
for it was wrong, which is why it was collapsed before the cost was known.
Cost is the only reason it might be worth restoring.

Two behaviours are load-bearing and easy to lose while rearranging this, both
verified in `b1f5db2` and neither obvious from the shape. `ABSENT` must not
pass `None` through, or `comparing(f)` silently sorts nulls last instead of
raising out of the extractor as `NullPlacement` documents. And the null check
must run for a bare comparator segment (`extractor is None`), or a tie-break
segment appended to a tolerant chain silently stops tolerating null elements,
against `then_comparing()`'s documented rule.
