## Why

`for_each_ordered()` computes, by hand, the branch `_split_point()` already
computes for every other order-observing terminal:

```python
executor = SEQUENTIAL if self._is_ordered() else None  # stream.py:541
return await self._evaluate(_ForEachSink(consumer), True, executor)
```

```
  _split_point() clause 3:   observes_order and is_ordered(chain)
  for_each_ordered():        True            and self._is_ordered()
```

Those are the same condition. Before `order-racing-delivery` (2026-08-28) they
were not — there was no such thing as an ordering demand originating at a
terminal, so the only way to get encounter order was to opt out of racing
altogether. That change added the concept and deliberately left this terminal
alone: its first non-goal was that it was fixing a wrong answer, and this
alters a right one. The roadmap predicted the item would halve once it landed.
It did, and this is the half that is a straight deletion.

The cost of the hand-rolled branch is not just duplication. Naming `SEQUENTIAL`
forfeits **all** concurrency, where the barrier forfeits only the reordering of
delivery — so an ordered `.parallel()` pipeline ending in `for_each_ordered()`
races nothing today, while the same pipeline ending in `collect(to_list())`
races everything and delivers in the same order.

```
  today                                after
  .parallel().map(f).for_each_ordered(g)

  src -[map f]-> g          src -+[map f]+
        ^ one worker,             +[map f]+- reorder -> g
        the .parallel() is        +[map f]+   ^
        silently discarded        +[map f]+   only delivery is ordered
```

Java splits the same way — `ForEachOps.OfRef.evaluateParallel()` picks
`ForEachOrderedTask` or plain `ForEachTask` on whether `ORDERED` is known
upstream — and `ForEachOrderedTask` is still a fork-join task. It does not
drop to a sequential traversal, which is what naming `SEQUENTIAL` here does.

## What Changes

- **`for_each_ordered()` stops naming `SEQUENTIAL`.** Its body becomes the one
  line `for_each()` already is, with `True` where `for_each()` passes `False`:

  ```python
  return await self._evaluate(_ForEachSink(consumer), True)
  ```

  The consumer is still invoked in encounter order on an ordered pipeline, and
  still released from that guarantee on an unordered one — clause 3 is gated on
  `is_ordered(chain)` exactly as the deleted branch was.
- **An ordered racing `for_each_ordered()` now races its chain.** This is the
  behaviour gain, and it is what the deletion buys rather than a side effect of
  it. Every op runs across all branches; only the handing of finished elements
  to the consumer is ordered.
- **BREAKING (behavioural, narrow): a side-effecting op *upstream* of
  `for_each_ordered()` no longer runs in encounter order.** `.parallel().peek(p)
  .for_each_ordered(g)` invokes `g` in encounter order as before, but `p` now
  fires concurrently and out of order. Java promises encounter order for the
  *action* and never for upstream stages, so this is a parity gain, but it is
  observable and takes a README migration-log entry.
- **`_evaluate()`'s `executor` parameter is not removed here.** `find_first()`
  is its other caller; it goes in `collapse-find-first-onto-barrier`. Nor does
  `Stream._is_ordered()` go — contrary to the roadmap's "what disappears" list,
  `for_each_ordered()` is not its sole caller. `Stream.concat()` uses it at
  `stream.py:402` to decide whether the concatenation inherits `unordered()`,
  and names `SEQUENTIAL` on the line above it. Both survive this change and the
  next one.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `stream-foreach-ordered`: the requirement that an unordered pipeline runs
  "under the stream's own executor rather than forcing sequential execution"
  loses its contrast — the ordered case no longer forces sequential either.
  Both cases now run under the stream's executor and differ only in whether the
  delivery barrier engages. A new requirement states that the ordered case does
  not serialize the chain, with the concurrency scenario that pins it.
- `stream-execution-model`: the sentence "`for_each_ordered()` SHALL do this
  when the pipeline is ordered, and SHALL otherwise run under the stream's own
  executor" is removed, along with its scenario asserting the chain "is driven
  under the sequential executor". `for_each_ordered()` joins the terminals that
  declare they observe encounter order and follow the stream's executor, and the
  requirement is retitled "... and only find_first() names one" — again a
  REMOVED plus ADDED pair, for the same reason.
- `racing-encounter-order`: the exemption "`find_first()` and
  `for_each_ordered()` are unaffected: each names the sequential executor at its
  own call site" loses `for_each_ordered()`, which moves into the list of
  terminals that observe encounter order. The existing "Restoring order for
  delivery SHALL NOT serialize the chain" requirement then governs it.
- `terminal-sinks`: the requirement "An ordered drive is available regardless of
  stream mode" currently says `for_each_ordered()` "SHALL use it
  unconditionally". That clause and its scenario go, and the requirement is
  restated as "... and find_first() is its only user" — a REMOVED plus ADDED
  pair rather than a MODIFIED, because both its title and two of its scenario
  names stop being true, and a MODIFIED requirement may not drop scenarios. It
  survives this change with `find_first()` as its only user, and is removed
  outright by `collapse-find-first-onto-barrier`.

  Restating it forces a decision on its scenario "An unordered parallel
  `find_first()` still races ... behaves as `find_any()` does". **That scenario
  is already wrong today** — it contradicts both `stream-find-first` and the
  shipped implementation, being the same stale rule
  `order-stateful-ops-under-racing` corrected in `stream-execution-model` and
  missed in this file. It is dropped here rather than restated, with the reason
  recorded in the delta. This is the one piece of scope in this change that is
  not `for_each_ordered()`'s, and carrying a knowingly-false scenario forward
  was the only alternative.

## Impact

- `src/snakestream/stream.py`: `for_each_ordered()` loses three lines and its
  docstring's Java citation is rewritten around `ForEachOrderedTask` still being
  a fork-join task rather than around the ordered/unordered task split.
- `README.md`: migration-log entry for the upstream-side-effect ordering change.
- Tests: any test asserting that an ordered parallel `for_each_ordered()` runs
  single-flight; new coverage that it races upstream while delivering in order.
- **No change to `execution.py`, `sink.py` or `ops.py`.** The mechanism this
  change moves onto already exists and is already exercised by every other
  order-observing terminal. This is a deletion at one call site.
- **Sequencing:** independent of `collapse-find-first-onto-barrier` except for
  the shared `terminal-sinks` requirement, which this change edits and that one
  deletes. Landing this first is the cheaper order; landing them in the other
  order means this change edits a requirement that no longer exists.
