## Why

Third and last of the sequence `add-free-threaded-ci-leg` opened and
`fork-join-executor-and-spliterator` unblocked. The roadmap has carried this
item behind those two since 2026-09-01, and the objection it was parked on is
now spent — recorded there as finding (b):

> "Java may combine on associativity alone because `Spliterator` splits into
> *contiguous* ranges. `race_through()` does not split, it steals: branches
> pull from one shared iterator under a lock, so their partitions interleave,
> and combining interleaved partials demands *commutativity* — which Java does
> not require."

`race_through()` no longer exists, and `Spliterator.try_split()` guarantees
contiguity by spec — the `stream-spliterator` capability names it the
load-bearing property for exactly this reason. Merging contiguous partitions
left-to-right in batch order is sound on associativity alone.

**The second reason is a measured gap, and it is the larger one.** Work placed
*inside* a collector gets no parallelism at all today, because `_ForkJoin`
inherits the generic `value()` — batches run the chain in worker threads, but
`_drain()` feeds every element into one terminal sink on the main loop.
Measured, free-threaded, n=4000, 4 workers:

| where the work is | sequential | parallel | speedup |
|---|---:|---:|---:|
| in the chain — `.map(slow).collect(to_list())` | 375.8ms | 159.1ms | **2.36x** |
| in the collector — `grouping_by(slow_key)` | 409.6ms | 419.3ms | **0.98x** |
| in the collector — `to_map(slow_key, cheap)` | 406.2ms | 409.1ms | **0.99x** |
| trivial collector — `.map(slow).collect(counting())` | 409.3ms | 172.9ms | **2.37x** |

A caller who puts a slow classifier in `grouping_by()` gets nothing from
`.parallel()`. Making only the *parameter* live would leave that cliff in
place, and worse, would make a hand-rolled
`collect(dict, my_accumulate, my_merge)` faster than the library's own
collector for the same job, with nothing in the API to explain why.

## What Changes

- **NEW**: a partition protocol on `TerminalSink`. A terminal that can be
  partitioned exposes the ability to spawn a peer accumulation and to merge
  one peer's container into another. Everything else keeps today's single
  container.
- **NEW**: `_ForkJoin.value()` overrides the generic `_drain()` form. Where the
  terminal partitions, each batch accumulates into its **own** container inside
  its worker thread, and the containers are merged in **batch order**. Where it
  does not, behaviour is exactly as today.
- **`collect(supplier, accumulator, combiner)`'s combiner starts being
  invoked.** It has shipped inert since 2026-08-17; README's row says so and
  stops needing to.
- **NEW public API**: `reduce(identity, accumulator, combiner)`, Java's third
  `reduce` overload. Note what it does *not* add — the type widening is already
  on the two-argument form, whose `Accumulator` is `(T | R, T) -> T | R`, so the
  combiner is the whole of the addition.
- **Leaf combiners** on the collectors whose merge is associative over their
  accumulation type: `to_list`, `to_set`, `to_collection`, `counting`,
  `joining`, `summing_int`/`summing_long`, `summarizing_int`/`summarizing_long`,
  `min_by`/`max_by`, `reducing`, and the two-argument `to_map`.
- **Derived combiners** on the composing collectors, from their downstream, by
  the rule `characteristics` already uses: `grouping_by`, `partitioning_by`,
  `mapping`, `collecting_and_then`. A composite whose downstream has no combiner
  has none either, and degrades to today's behaviour rather than to a wrong
  answer.
- **Deliberately excluded, each with its reason in the spec:**
  - `summing_double`, `averaging_int`/`long`/`double`, `summarizing_double` —
    **float addition is not associative**, so partitioning would change the
    result. All three `averaging_*` are excluded, not just the double: they
    share one `_averaging()` whose `_AvgBox.total` is a `float`. This is the
    same family README already excludes from `UNORDERED`, on a stronger reason:
    `UNORDERED` is about delivery order, a combiner is about associativity.
  - `to_map(key_mapper, value_mapper, merge_function)` — a caller-supplied
    merge is not required to be associative, so it cannot be lifted into a
    combiner. The two-argument form partitions; the three-argument form does not.

## Capabilities

### New Capabilities

- `parallel-reduction`: when a terminal is partitioned, how partitions are
  merged, and the contract a caller's `combiner` and `identity` must satisfy
  for a partitioned result to equal the sequential one.

### Modified Capabilities

- `collector-protocol`: `Collector.combiner` stops being inert.
- `mutable-reduction-collect`: the three-argument `collect()`'s combiner is
  invoked under a partitioning executor.

**Per-collector deltas are enumerated in `tasks.md` section 4** — each collector
gaining or explicitly declining a combiner needs its own capability's delta, and
they are written as that section is worked rather than guessed at here. The same
shape `fork-join-executor-and-spliterator` ended up in, where the delta set grew
from 3 to 15 once the requirements were read individually.

## Impact

- `src/snakestream/sink.py` — the partition protocol on `TerminalSink`
- `src/snakestream/execution.py` — `_ForkJoin.value()` override
- `src/snakestream/collector.py` — `CollectorSink` partitioning
- `src/snakestream/collectors.py` — leaf and derived combiners
- `src/snakestream/terminals.py` — `ReduceSink` partitioning
- `src/snakestream/stream.py` — the third `reduce` overload
- `README.md` — two parity rows stop saying "not invoked" / "not implemented";
  Migration entries for both
- `roadmap.md` — the last of the three sequenced **Later** items resolves
