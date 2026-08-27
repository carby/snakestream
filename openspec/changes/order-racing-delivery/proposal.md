## Why

Whether a racing pipeline delivers its elements in encounter order currently
depends on whether an ordering barrier happens to exist upstream:

```
  .parallel().map(f).collect(to_list())            -> scrambled
  .parallel().sorted(c).map(f).collect(to_list())  -> in order   (accidentally)
  .parallel().limit(8).map(f).collect(to_list())   -> in order   (accidentally)
  .parallel().unordered().limit(8).map(f)          -> scrambled
```

`order-stateful-ops-under-racing` introduced the middle two while fixing a
wrong answer, and deliberately declined to reconcile them with the first. The
result is a seam a caller cannot reason about: nothing in the pipeline they
wrote says which behaviour they get.

The reconciliation is not an open question. This project's guiding principle is
that a divergence from Java's *internals* is not a defect but a divergence in
observable *API behaviour* is — the framing that found the position-dependent
`.parallel()` bug. Java's ordered parallel streams preserve encounter order
into `collect`. `.parallel().map(f).collect(to_list())` returning a scrambled
list is therefore the defect, and the accidental in-order delivery behind a
barrier is the code drifting toward the right answer. The rule "racing does not
preserve encounter order" is what has to go.

`unordered()` is already spec'd as the lever that buys concurrency back, and
already advertised as a performance lever rather than only a semantic one. This
change makes that its primary job.

## What Changes

- **BREAKING: an ordered racing pipeline delivers in encounter order.**
  `.parallel().map(f).collect(to_list())` returns elements in source order.
  Callers who want today's behaviour declare `.unordered()`, which is the
  documented lever and is measurably faster. This is a behaviour break for
  anyone relying on the scramble, and belongs in README's migration log.
- **The barrier moves to where it was always needed: the end of the chain.**
  Restoring order at index 0 would serialise everything — with an empty head
  the whole chain lands in the ordered tail. The demand belongs at the
  *terminal*, i.e. a split at `len(chain)`: every branch races the whole chain
  and only delivery is reordered, which is Java's shape and costs no
  per-element concurrency.

```
  today, ordered + barrier at 0        after: barrier at len(chain)
  -----------------------------        ----------------------------
  src - reorder -[map f]---> out       src -+[map f]+
        ^ nothing races                     +[map f]+- reorder -> out
        (effectively sequential)            +[map f]+   ^
                                            +[map f]+   only delivery is ordered
```

- **A terminal declares whether it observes encounter order**, and the
  delivery barrier engages only when it does *and* the pipeline is ordered
  there. `count()`, `for_each()`, `any_match()` and `find_any()` do not
  observe it and pay nothing. `collect()` asks its collector, reading the
  `UNORDERED` characteristic `add-collector-characteristics` ships — which is
  what that change is a prerequisite for, and the first thing to read it.
- **`iterator()` delivers in encounter order too** on an ordered racing
  stream. It hands raw elements to the caller, so order there is definitionally
  observable; `stream-iterator`'s current scenario says "racing branches,
  unordered" and moves with this.
- **`_resume_point()` is replaced rather than tuned.** Today an ordered tail
  resumes racing only at an explicit `unordered()`, because racing an
  order-blind suffix would scramble delivery. Once delivery is reordered at the
  terminal that objection is gone: the barrier op itself runs in one ordered
  pass and **everything after it races**. `.limit(n).map(fetch)` gets its
  concurrency back — the case the roadmap opened this item on.
- **`unordered()` keeps its exact current meaning** and gains reach. It clears
  the characteristic for what follows, so a pipeline unordered at the terminal
  has no delivery barrier. No new API, no new mode, no new executor.

### Non-goals

- **`find_first()` and `for_each_ordered()` are not touched.** Both name
  `SEQUENTIAL` at their own call site and keep doing so here. Collapsing them
  onto this mechanism is the roadmap's **Next** item 2, deliberately separate:
  this change alters a wrong answer, that one alters a right one, and merging
  them would make a single change that both breaks behaviour and rewrites two
  correct terminals.
- **Marking collectors Java leaves unmarked.** `counting()`, `summing_*()`,
  `grouping_by()` and the rest are order-blind in fact but `CH_ID`/`CH_NOID` in
  OpenJDK; `add-collector-characteristics` matched Java exactly and handed the
  divergence here. It is **still deferred**: this change should land at parity
  and be measured first. Marking them is a follow-up with a benchmark
  attached, not a line slipped into this one.
- **`_READ_AHEAD`'s export.** It becomes the throughput/memory knob for every
  ordered racing pipeline once this lands, which is what unblocks the
  roadmap's item 3 — but exporting and renaming it is that item's work.

## Capabilities

### Modified Capabilities

- `racing-encounter-order`: the central change. The capability currently
  defines order restoration as something an *operation* requires; it must also
  define it as something *delivery* requires. The "an unordered pipeline takes
  the order-blind path" requirement stands unchanged and becomes the primary
  path for callers who opt out. Adds the terminal-observes-order rule and what
  it costs.
- `stream-execution-model`: "A terminal uses the stream's executor unless it
  names one, and find_first() always names one" gains the terminal's ordering
  declaration — a second axis alongside which executor it names. `find_first()`
  and `for_each_ordered()`'s existing wording is untouched.
- `stream-iterator`: "iterator() works identically for sequential and parallel
  streams" — its racing scenario says the yielded elements are unordered, which
  ceases to be true for an ordered stream.
- `collector-protocol`: `Characteristics.UNORDERED` is currently spec'd as a
  declaration that changes no collected result. That requirement is what this
  change falsifies: it is now read, and it now decides whether a racing
  `collect()` pays the delivery barrier.

## Impact

- **Code**: `execution.py` (the delivery barrier in `race_through()`,
  `_split_point()`'s terminal clause, `_resume_point()`'s replacement,
  `Executor.value()`/`elements()` carrying the demand), `stream.py` (terminals
  declaring it, `iterator()`), `collector.py`/`collectors.py` (reading
  `characteristics` — no new declarations).
- **Public behaviour**: ordered racing pipelines change delivery order.
  Migration-log entry, README ordering prose, and `CLAUDE.md`'s "racing
  destroys encounter order" framing all move.
- **Performance**: ordered racing pipelines gain reorder buffering and
  head-of-line blocking by default, bounded by `_READ_AHEAD`; ordered pipelines
  behind a mid-chain barrier *gain* concurrency in their suffix. Both
  directions want measuring, and `unordered()` must be shown to be the faster
  path — the spec already promises it is.
- **Depends on**: `add-collector-characteristics` (for `UNORDERED`).
  **Unblocks**: roadmap **Next** items 2 and 3.
