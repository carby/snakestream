# Benchmark findings

Two harnesses ship with this change, both kept rather than deleted so the
figures design.md and proposal.md cite can be reproduced.

- `bench_shared_tail.py` - the roadmap item's own question: what does sharing
  the six-line tail behind one more call cost? Run first, and it is what
  established the constant this change is built on.
- `bench_specialize.py` - this change's shape against the baseline, the shared-
  tail shape and a null test.

Both need three or four sibling modules on `PYTHONPATH`: `comp_baseline.py` (a
verbatim copy of `src/snakestream/comparator.py` at the pre-change commit),
`comp_null.py` (byte-identical to it), `comp_shared.py` (baseline plus
`_compare_keys`) and `comp_plan.py` (this change's shape). Build the first two
by copying `comparator.py`; build `comp_plan.py` by applying `prototype.diff`,
which ships beside these harnesses and applies cleanly to `comparator.py` at
the pre-change commit. `prototype.diff` is the measured prototype, not the
final shape - it still carries the `C901` finding under Gates and the stale
`_norm` docstrings task 6.1 rewrites.

**Protocol.** 2000 pairs per sample; comparators built once per shape rather
than once per sample (this is what drops the noise floor from ~2% to ~0.2% -
the first run built them per sample and its figures should not be used); order-
balanced rotation, so a drift in system load cannot settle on one
implementation; min and median over 300-1000 rounds depending on shape cost.
A **null test** - the baseline against a byte-identical copy of itself - runs in
every shape as the floor. WSL2, Python 3.14 free-threaded build, one machine.

## Finding 1: sharing the tail costs a constant, not a percentage

The roadmap item `segment-sign-sharing-cost` reported ~3.3% and scoped it to
chains that are both async and null-tolerant. Both halves of that are wrong.

| shape | baseline ns/cmp | shared, d ns (min/med) | shared, d % (min/med) | null floor d % |
|---|---|---|---|---|
| sync tolerant | 268.3 | +11.8 / +12.2 | +4.40% / +3.72% | -0.89% / -1.52% |
| sync intolerant | 265.3 | +8.9 / +10.2 | +3.34% / +3.15% | -1.05% / -1.14% |
| async tolerant, cheap extractor | 548.8 | +15.3 / +17.0 | +2.78% / +2.76% | -0.01% / +0.11% |
| async intolerant, cheap extractor | 538.1 | +14.0 / +18.9 | +2.61% / +2.97% | -0.42% / +0.19% |
| async tolerant, canonical extractor | 3759.9 | +31.0 / +47.1 | +0.83% / +1.12% | -0.42% / +0.09% |
| async intolerant, canonical extractor | 3756.0 | +17.7 / +14.0 | +0.47% / +0.33% | +1.54% / +0.68% |

The delta in nanoseconds is flat; the delta in percent is that constant over the
denominator. **Sync is the worst case, not the exempt one** - a fixed frame
shows up largest where the comparison is cheapest, and sync `comparing(f)` at
268ns is the cheapest thing here. The item's original figures were taken against
the cheapest possible async extractor, the same denominator trap
`merge-segment-sign-on-natural-ordering`'s closing entry already warns about.

"Cheap" is a bare `async def f(x): return x`. "Canonical" is the
`await asyncio.sleep(0)` extractor `bench_segment_sign.py` ships with in
`openspec/changes/archive/2026-09-07-merge-segment-sign-on-natural-ordering/`.

## Finding 2: specializing at construction is negative everywhere

| shape | baseline ns/cmp | **plan** d(min) | shared-tail d(min) | null floor d(min) |
|---|---|---|---|---|
| sync, one key segment | 265.8 | **-14.53%** (-38.6 ns) | +3.71% | -1.84% |
| sync, comparator segment | 293.5 | **-10.73%** (-31.5 ns) | +4.20% | -1.78% |
| sync, two-segment chain | 264.7 | **-14.17%** (-37.5 ns) | +4.40% | -1.38% |
| sync tolerant, 10% None | 276.5 | **-10.19%** (-28.2 ns) | +2.84% | -2.18% |
| async cheap, one key segment | 543.2 | **-18.65%** (-101.3 ns) | +2.32% | +0.18% |
| async cheap tolerant, 10% None | 549.2 | **-14.85%** (-81.5 ns) | +3.53% | +1.11% |
| async cheap, mixed chain | 553.7 | **-20.07%** (-111.2 ns) | +0.50% | -1.26% |
| async canonical, one key segment | 3778.5 | **-3.36%** (-127.0 ns) | -0.61% | -1.27% |
| async canonical tolerant, 10% None | 3650.2 | **-6.34%** (-231.5 ns) | -2.09% | +0.26% |

Negative in all nine shapes, min and median agreeing, outside the floor in every
row. The **mixed chain** (an async segment followed by a sync one) is the
largest win and confirms the mechanism: under the baseline a sync segment on an
async chain allocates two coroutines - `_segment_sign_async` and
`_extract_pair_async` - to await nothing.

The canonical rows are smaller in percent for the same reason Finding 1
describes: `await asyncio.sleep(0)` dominates the denominator. They are the
*larger* wins in nanoseconds.

## Finding 3: construction is the cost, and it is repaid in ~11 comparisons

Min of 60 rounds x 20,000 builds, ns per comparator constructed.

| shape | baseline | plan | d ns | d % | null d% |
|---|---|---|---|---|---|
| `comparing(f)` | 1904.5 | 2292.5 | +388.1 | +20.38% | +0.17% |
| `comparing(f, cmp)` | 3320.1 | 3981.6 | +661.5 | +19.92% | +3.63% |
| 3-segment chain | 21404.4 | 23696.5 | +2292.1 | +10.71% | +1.05% |
| `nulls_first(comparing(f))` | 3897.1 | 4806.8 | +909.7 | +23.34% | +0.25% |
| `comparing(async f)` | 942.1 | 1437.5 | +495.4 | +52.58% | +0.06% |

Against a saving of ~30-40ns per sync comparison and ~100ns per async one,
break-even is ~11 comparisons on a sync chain and ~5 on an async one.
`min()`/`max()`/`min_by()`/`max_by()` perform n-1 over a stream, so anything
past a dozen elements is pure win. `sorted()` is unaffected either way - it
reads `.segments` and never enters `__call__`.

## Correctness

The prototype was validated against the verbatim baseline across **26 comparator
shapes x 49 input pairs = 1274 comparisons**, comparing both the returned sign
and the exception type raised: nulls first and last, null *keys* (an extractor
returning `None` for a non-`None` element), both-`None` ties, descending,
reverse-before and reverse-after chaining, bare comparator segments, chains
mixing sync and async segments, contract violations, and the construction-time
async-comparator rejection. **Zero mismatches.** `.segments` keeps its shape.

## Gates

`ty check` passes clean on the prototype. `ruff format --check` clean.
`ruff check` reports one finding to resolve during implementation:
`C901 _build_compare is too complex (11 > 10)`, the nested closures counting
toward the enclosing function.
