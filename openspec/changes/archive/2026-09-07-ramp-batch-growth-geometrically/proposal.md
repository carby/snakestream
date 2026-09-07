## Why

The fork-join executor grows its batch size in one step: round one pulls
`_FIRST_BATCH_SIZE` (4) per worker, and every refill after that jumps straight
to `BATCH_SIZE` (1024). That 256x step is a cliff. Measured on
`.parallel().peek(fn).any_match(x == k)` over 100k elements, one extra element
past the first round costs 4096 chain invocations:

```
answer at k= 10 : chain ran on    16 elements
answer at k= 17 : chain ran on  4112 elements
```

`CLAUDE.md` already concedes that every reason the old racing window existed —
memory held resident, latency behind a straggler, wasted upstream invocations
under a short-circuiting terminal — "still applies at this size". This is where
that concession becomes actionable. `unordered()`, the documented lever, does
not help: the order-blind path is the one that escalates fastest.

Task 7.2 of `fork-join-executor-and-spliterator` measured a smoother curve and
rejected it, but it measured a **Java-style arithmetic** rule (`+4` per round),
which never saturates and multiplied dispatches ~10x (12 -> 126 at n=8192). A
**geometric** rule saturates in logarithmic time, so its extra cost is a small
constant rather than a multiplier. That distinction was never tested, and it
inverts the verdict.

## What Changes

- Both `_fork_join_ordered_batches()` and `_fork_join_unordered_batches()` in
  `execution.py` replace `size = BATCH_SIZE` with a geometric ramp,
  `size = min(size * 8, BATCH_SIZE)`, seeded at one element per worker.
- **`_FIRST_BATCH_SIZE` is deleted.** Its own comment calls it "a starting
  point, not a measurement". Seeding the ramp at `1` measured strictly better
  than seeding it at `4` and needs no named constant to justify: the rule is
  "one element per worker, x8 per refill, capped at `BATCH_SIZE`".
- **BREAKING (internal, silent):** `find_first()`'s documented over-invocation
  bound tightens from `WORKERS * _FIRST_BATCH_SIZE` (16) to `WORKERS` (4), and
  the symbol the spec names ceases to exist. No public name changes; `WORKERS`
  and `BATCH_SIZE` are untouched.

Measured, GIL build, `WORKERS=4`, `BATCH_SIZE=1024`:

| rule | waste @k=1 | @17 | @20 | @100 | dispatches n=8192 | n=100k |
|---|---:|---:|---:|---:|---:|---:|
| shipped, one-step 4 -> 1024 | 16 | 4078 | 4082 | 4087 | 12 | 102 |
| rejected in 7.2, +4/round | - | - | - | - | 126 | - |
| seed 1, x8 | 4 | 35 | 59 | 269 | 20 | 109 |

Draining `count()` wall time is unchanged within noise on the GIL build
(n=100k: 518ms shipped vs 400ms ramped, individual reps overlapping); the
dispatch count is the honest metric and it grows by a constant, not a factor.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `racing-encounter-order`: the read-ahead requirement's accepted over-pull
  allowance is restated against a ramped bound rather than a fixed one — the
  in-flight amount is no longer a single steady-state number a pipeline reaches
  immediately, and the accepted waste under an order-blind short-circuiting
  terminal is now bounded by how far the ramp has climbed when the terminal
  settles, not by `WORKERS * BATCH_SIZE`.
- `stream-find-first`: "The number of such elements SHALL be bounded ...
  `WORKERS` batches of up to `_FIRST_BATCH_SIZE` elements each" names a symbol
  this change deletes, and the bound it states tightens to `WORKERS`.

## Impact

- `src/snakestream/execution.py` — the two growth lines, the
  `_FIRST_BATCH_SIZE` definition and its comment block.
- Tests asserting the first-round bound: `tests/test_racing_encounter_order.py`
  imports `_FIRST_BATCH_SIZE` by name (task 4.3 of
  `fork-join-executor-and-spliterator` records the rename into it).
- `CLAUDE.md`'s "Read-ahead has no bespoke bound any more" paragraph, which
  states the steady state as `WORKERS * BATCH_SIZE` reached after the first
  round, and names `_FIRST_BATCH_SIZE`.
- Not in scope: the free-threaded small-source cliff this ramp also fixes.
  That is a different claim — worker utilisation, not a read-ahead bound — and
  is proposed separately as `spread-small-sources-across-workers`.
