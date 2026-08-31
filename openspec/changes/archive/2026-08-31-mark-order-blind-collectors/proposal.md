## Why

The roadmap's open question 4 asks whether `counting()`, `summing_int/long()`
and `summarizing_int/long()` should declare `Characteristics.UNORDERED`. Its own
rule — three deferrals, so the next pass either brings a benchmark or the answer
is no — made this the session that decides. The benchmark was run, and it
contradicts the premise both the item and `race_through()`'s docstring rest on.

The docstring claims the delivery barrier costs "nothing at all on IO-bound
work". That figure came from 40 elements at a **uniform** 10 ms, where the
reorder buffer cannot stall by construction — the barrier is free by assumption,
not by measurement. Under *tail* latency, which is what real IO has, the barrier
costs 1.12–1.27x by exhausting the `_READ_AHEAD` window behind a straggler:

| shape | unmarked | marked | |
|---|---|---|---|
| 20k elements, `map(x+1)` (too cheap to race) | 9.43 µs/elt | 7.12 µs/elt | 1.33x |
| 40 elements, uniform 10 ms | 106.9 ms | 107.6 ms | none |
| 60 elements, every 10th 100 ms, rest 5 ms | 338.1 ms | 265.3 ms | 1.27x |
| 200 elements, 90% 2 ms / 10% 50 ms | 550.8 ms | 485.9 ms | 1.13x |

So the mark buys something on the shape racing exists for, not only on the shape
nobody should race. That is what flips the answer from "no" to "yes".

The second half of the change answers the reasonable objection that an
optimization with no test behind it gets lost in a future refactor. The guard
that answers it already works: `test_to_set_takes_the_order_blind_path` asserts
that `to_set()` declares `UNORDERED`, and the `grouping_by`/`partitioning_by`
recording tests pin `collect()`'s acting on that declaration, so both ways the
order-blind path can be lost already fail loudly.

What is missing is not the guard but the *rule*. Nothing states that the
correctness assertion sitting beside that declaration check is not what does the
work — and for a collector declaring `UNORDERED` it cannot be, since the result
is correct under either path. `collector-protocol` and `racing-encounter-order`
each carry a scenario asserting `to_set()` engages **no reorder barrier**, and
neither says how such a scenario is discharged when the result cannot betray
arrival order. Marking four more collectors of exactly that kind is the moment
to write the rule down, so the next person to add one does not reach for a
correctness-only assertion, or for a wall-clock threshold.

## What Changes

- `counting()`, `summing_int()` and `summing_long()` declare
  `Characteristics.UNORDERED`.
- `summarizing_int()` and `summarizing_long()` declare it too: `SummaryStatistics`
  is a `NamedTuple`, so `==` is structural, and count/sum/min/max/average over
  `int`s are each order-invariant.
- `summing_double()`, `averaging_int/long/double()` and `summarizing_double()`
  are stated as permanent non-declarers rather than left silent — float addition
  is not associative, so they are order-*sensitive in fact*, a firmer exclusion
  than a merely undeclared one.
- The barrier-skip gains a stated verification rule, because for these
  collectors the skip is **unobservable through the public API**: `counting()`
  returns `20` in any order. A result that cannot betray arrival order SHALL be
  guarded by the declaration assertion plus the already-pinned mechanism, not by
  a timing measurement.
- `test_to_set_takes_the_order_blind_path` gains a cross-reference to the tests
  that pin the other half of its guard, so the pair reads as one guard rather
  than two unrelated tests.
- `race_through()`'s docstring is corrected: the "nothing at all on IO-bound
  work" claim is replaced with the uniform-vs-tail distinction and its figures.

Not breaking. A collector's declared characteristics are public surface, but
`UNORDERED` never changes the value a correct collector produces, and under
`SEQUENTIAL` it has no effect at all.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `collector-counting-summing-averaging`: `counting()`, `summing_int()` and
  `summing_long()` gain a requirement to declare `UNORDERED`; the `*_double` and
  `averaging_*` family gains a requirement **not** to.
- `collector-summarizing`: `summarizing_int()`/`summarizing_long()` gain a
  requirement to declare it, resting on `SummaryStatistics`'s structural `==`;
  `summarizing_double()` a requirement not to.
- `racing-encounter-order`: gains a requirement stating how a barrier-skip is
  verified when the collected result cannot betray arrival order, and scenarios
  covering the newly marked collectors.
- `collector-to-set`: its existing "declaration SHALL be true of the behaviour
  and not merely asserted" requirement gains an explicit statement of how that
  is discharged for a `set`, whose result compares equal under either path. This
  codifies what the shipped test already does rather than changing it; it is in
  scope because `to_set()` is the worked example the new rule generalizes from.

## Impact

- `src/snakestream/collectors.py` — the marks, and the long comment in
  `counting()` that currently defers this question.
- `src/snakestream/execution.py` — `race_through()`'s docstring figures only; no
  behaviour change.
- `tests/test_racing_delivery_order.py` — the `to_set` cross-reference, plus
  coverage of the marked collectors.
- `roadmap.md` — question 4 moves to **Done**; note that item 5's enumeration
  must no longer carry it forward.
- No change to `collect()`'s dispatch: it already reads `characteristics`, and
  that read is already pinned by the `grouping_by`/`partitioning_by` recording
  tests. This change adds declarations, not mechanism.
