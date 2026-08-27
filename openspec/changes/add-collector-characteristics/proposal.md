## Why

Java's `Collector<T,A,R>` carries a characteristics set; snakestream's carries
none. That is a gap in the public surface the library otherwise matches 1:1,
and it is the gap the **Next** roadmap's item 1 (an ordered racing pipeline
delivers in encounter order) needs closed before it can start: `UNORDERED` is
the only vocabulary a collector has for saying it does not observe encounter
order, and therefore need not pay the reorder barrier's head-of-line cost.

Shipping it separately from item 1 is deliberate. It is justified on parity
alone, it keeps item 1 about ordering, and it touches a disjoint set of files —
`collector.py` and `collectors.py` here, against `execution.py` there.

## What Changes

- **`Collector` gains a `characteristics` parameter and attribute**, holding a
  frozenset of a new `Characteristics` enum. It is the fifth and last
  constructor parameter, after `finisher`, and defaults to empty — so every
  existing `Collector(...)` call, in this library and in user code, is
  unaffected. Not a breaking change.
- **`Characteristics` ships one member: `UNORDERED`.** The enum is shaped to
  admit Java's other two later; neither is added now:
  - `IDENTITY_FINISH` is already inferable from `finisher is None`, so adding
    it would introduce a second way to state one fact, and a way for the two
    to disagree.
  - `CONCURRENT` describes a collector safe to accumulate into one shared
    container from multiple partitions. Snakestream has no partitioned
    execution to be concurrent *with* — the `combiner` is accepted for
    signature parity and never invoked — so the member would be unreadable by
    anything. It belongs with the real-parallelism work in the roadmap's
    **Later**.
- **`to_set()` declares `UNORDERED`.** It is the only factory in
  `collectors.py` whose Java counterpart carries the characteristic (see the
  note below), and its result genuinely cannot observe the order it was fed.
- **`mapping()` and `collecting_and_then()` inherit their downstream's
  characteristics**, matching Java, where both derive rather than fix their
  own. `grouping_by()` and `partitioning_by()` take a downstream too but do
  **not** inherit: in Java their own characteristics are fixed regardless of
  downstream, because the downstream's result is a map *value*, not the
  collector's own result.
- **Nothing reads the characteristic yet.** This change ships the vocabulary
  and the declarations; item 1 is what makes `UNORDERED` observable. That is
  stated rather than hidden — a declaration no code consults is the honest
  scope of a prerequisite.

### Non-goals

- **Marking collectors Java leaves unmarked.** `counting()`, `summing_*()`,
  `averaging_*()`, `summarizing_*()`, `grouping_by()`, `partitioning_by()` and
  `to_map()` are all *semantically* order-blind, and in snakestream marking
  them would let item 1 skip the barrier for them. Java marks none of them:
  OpenJDK gives `toSet()` `CH_UNORDERED_ID` and gives these `CH_ID` or
  `CH_NOID`, because Java's `UNORDERED` governs its combine strategy, where an
  associative reduction is safe either way and the mark buys nothing. Under
  item 1 the mark *would* buy something here. That is a real divergence to
  weigh, and it is item 1's to weigh — it needs the machinery that can measure
  the difference. This change matches Java exactly so that item 1 starts from
  parity rather than from a guess.
- **`Collector.characteristics()` as a method.** Java's is a method because
  `Collector` is an interface; snakestream's is a concrete class holding
  callables as plain attributes, and an attribute matches both the class and
  the existing four parts.

## Capabilities

### New Capabilities

None. The characteristic is a new part of an existing type, not a new
behaviour of its own.

### Modified Capabilities

- `collector-protocol`: the public `Collector` shape gains a fifth part,
  `characteristics`, with its default and its sync-only nature (it is data, not
  a callable, so the sync-or-async rule the other four carry does not apply).
  Adds the `Characteristics` enum and its single member to the public surface.
- `collector-to-set`: `to_set()` SHALL declare `UNORDERED`.
- `collector-mapping`: `mapping()` SHALL carry its downstream's
  characteristics.
- `collector-collecting-and-then`: `collecting_and_then()` SHALL carry its
  downstream's characteristics.

## Impact

- **Code**: `src/snakestream/collector.py` (the `Collector` class, the new
  enum), `src/snakestream/collectors.py` (three factories of the ~20 —
  `to_set`, `mapping`, `collecting_and_then`; the rest are untouched and keep
  the empty default).
- **Public API**: `Characteristics` joins the exported surface; README's parity
  table gains a row. Additive only — no rename, no migration-log entry.
- **Downstream**: unblocks the roadmap's **Next** item 1, which is the reason
  for the sequencing 4 → 1 → 2 → 3 recorded there.
- **Not affected**: `_CollectorSink`, `Stream.collect()`, `to_generator` and
  the `StreamingCollector` path, and every execution-side module. No terminal
  reads the characteristic until item 1.
