+++
id = "segment-sign-sharing-cost"
title = "Sharing the segment-sign tail costs one frame, ~10-19ns"
bucket = "now"
rank = 1
filed = 2026-09-08
updated = 2026-09-09
gate = "specialize-comparator-segments lands and measures negative in every shape - the shape that answers this was found and scaffolded; what remains is the implementation, not the decision"

[refs]
changes = ["specialize-comparator-segments"]
specs = ["comparator-contract", "comparator-null-ordering"]
files = ["src/snakestream/comparator.py"]
+++

`_segment_sign_sync` and `_segment_sign_async` differ only in extraction, which
is the only part of a segment that can await. Everything else about them is
duplicated, and every attempt to share it has measured a cost - originally
reported as ~3% on an async, null-tolerant chain, since re-measured and found
to be a **constant ~10-19ns per segment per comparison** whose percentage is
entirely a function of what the extractor costs.

**Half of it is already in the tree** (`b1f5db2`). Extraction is factored into
`_extract_pair_sync`/`_extract_pair_async`, collapsing four shapes into two and
replacing the `nulls is NullPlacement.ABSENT` two-arm split with one shared
`nulls is not ABSENT and (ea is None or eb is None)` guard. That commit is a
checkpoint: it carries the cost described below, deliberately and not yet
argued.

**What is still duplicated:** the six lines each twin ends with - the
`comparator is None` natural-ordering branch, the `type(sign) is not int`
contract check, and the return.

## The measurements

Re-measured 2026-09-09 (WSL2), sharing the six-line tail as
`_compare_keys(ea, eb, comparator)` against a verbatim baseline, with a **null
test** - the baseline benchmarked against a byte-identical copy of itself - as
the floor in every shape. 2000 pairs per sample, min and median over 600-1000
rounds on the sync and cheap-async shapes and 300 on the canonical ones,
order-balanced alternating rounds, comparators built once per shape rather than
once per sample. No `None` elements, so every comparison reaches the tail: the
maximum exposure to the extra call.

| shape | baseline ns/cmp | shared, d ns (min/med) | shared, d % (min/med) | null floor d % |
|---|---|---|---|---|
| sync tolerant | 268.3 | +11.8 / +12.2 | +4.40% / +3.72% | -0.89% / -1.52% |
| sync intolerant | 265.3 | +8.9 / +10.2 | +3.34% / +3.15% | -1.05% / -1.14% |
| async tolerant, cheap extractor | 548.8 | +15.3 / +17.0 | +2.78% / +2.76% | -0.01% / +0.11% |
| async intolerant, cheap extractor | 538.1 | +14.0 / +18.9 | +2.61% / +2.97% | -0.42% / +0.19% |
| async tolerant, canonical extractor | 3759.9 | +31.0 / +47.1 | +0.83% / +1.12% | -0.42% / +0.09% |
| async intolerant, canonical extractor | 3756.0 | +17.7 / +14.0 | +0.47% / +0.33% | +1.54% / +0.68% |

"Cheap" is a bare `async def f(x): return x`; "canonical" is the
`await asyncio.sleep(0)` extractor `bench_segment_sign.py` ships with in
`openspec/changes/archive/2026-09-07-merge-segment-sign-on-natural-ordering/`.
The delta in nanoseconds is flat across all six shapes; the delta in percent is
that constant divided by the denominator. On the canonical extractor it lands
at or under that shape's own noise floor, and anything awaiting real I/O -
the only reason to write an async key extractor at all - buries it.

**Dead ends, already tried:** a per-operand `_passes_through()` predicate and
an inline-everything shape with no helpers at all. Both are called twice as
often as `_compare_keys` for less work, and neither beat the two-arm original.
Hoisting the null check out of the tolerant arm was separately measured at
~3.1% on the original harness and is what is in the tree now; it has not been
re-measured under the protocol above, so treat its number as being on the old
basis.

## Why it is a real question and not a tidiness itch

The trade already has a precedent in this same file, on the same side:
`is_new_extremum`'s docstring records that delegating its contract check
"measured ~5%", which is why that check is written out at every call site
instead. If the answer here is the same, the deliverable is a comment
recording it - so the next reader stops where this one did - not a refactor.
That comment must state the constant, though. A percentage in it would be
wrong for every reader whose extractor differs from the harness's.

The path is `KeyComparator.__call__` only, since `sorted()` takes the
decorate-sort-undecorate column instead. Within it the exposure is widest on
plain sync `comparing(f)` - every `min()`, `max()`, `min_by()` and `max_by()`
comparison, one per element.

**The lead was tried and it won** (2026-09-09), and is scaffolded as
`specialize-comparator-segments`. Measured against a verbatim baseline it is
negative in all nine shapes - -10% to -20% on sync and cheap-async chains,
-3.4% to -6.3% on the canonical one - so the tail's frame is absorbed several
times over. Two things about the answer are worth carrying forward, because
neither is what this item expected. It does **not** reduce the tail to one
copy: natural ordering and the contract guard each still appear twice, moved
off the sync/async axis and onto tolerant/intolerant. And the justification is
performance, not de-duplication - which reverses this item's own framing, where
tidiness was the goal and cost the obstacle. See that change's design.md
Decision 3 and benchmark-findings.md. The description below is the lead as it
was stated before being measured.

**The lead worth trying before accepting** was to stop paying for the frame
rather than to place it better: specialize each segment into a closure at
construction, as `callable-dispatch` already does for awaitability and `_norm`
already does for `isinstance(payload, tuple)`. That deletes the
`_segment_sign_async` and `_extract_pair_async` coroutines per segment per
comparison, which at ~10-19ns a frame are worth several times the tail, and
leaves the sync/async twinning confined to the extractors - the one part that
genuinely awaits. It also moves the remaining duplication off the sync/async
axis and onto tolerant/intolerant. Unmeasured; the type checker is the known
risk, as it was for the prototype in
`merge-segment-sign-on-natural-ordering`.

## What the analysis corrected

The two-arm extraction shape was justified in both docstrings by the type
checker being unable to narrow through a compound `nulls is not ABSENT and
(...)` guard. **That reason never held** - the `cast("Any", ...)` those arms
already wrote leaves nothing to narrow. The shape was right and the argument
for it was wrong, which is why it was collapsed before the cost was known.
Cost is the only reason it might be worth restoring.

**This item's own scoping was backwards** (corrected 2026-09-09). It read
"sync chains and async intolerant chains were unaffected in every run" and
narrowed the path to "chains that are both async and null-tolerant". Measured
under the protocol above, sync is the *worst* case - +4.40%/+3.72% tolerant,
+3.34%/+3.15% intolerant, against a -1% floor - and the async, null-tolerant
chain with a realistic extractor is where the effect is least visible. That is
what the mechanism predicts once the cost is known to be a fixed frame rather
than a proportional tax: it shows up largest where the comparison is cheapest,
and sync `comparing(f)` at 268ns is the cheapest thing in the table. The
original figures were measured against the cheapest possible async extractor,
the same denominator trap `merge-segment-sign-on-natural-ordering`'s closing
entry already warns about.

Two behaviours are load-bearing and easy to lose while rearranging this, both
verified in `b1f5db2` and neither obvious from the shape. `ABSENT` must not
pass `None` through, or `comparing(f)` silently sorts nulls last instead of
raising out of the extractor as `NullPlacement` documents. And the null check
must run for a bare comparator segment (`extractor is None`), or a tie-break
segment appended to a tolerant chain silently stops tolerating null elements,
against `then_comparing()`'s documented rule.
