## Why

`unordered()` sets a boolean field on the stream instance, so it applies to the
whole pipeline no matter where it is written. Java's `unordered()` is a
*pipeline stage* that clears `ORDERED` for itself and everything downstream,
leaving upstream stages ordered — the deliberate opposite of `parallel()`,
which sets a field on the source stage precisely so that it *is*
position-independent. We copied `parallel()`'s rule onto `unordered()` and lost
the distinction.

That is not merely cosmetic. Because a field cannot be re-set by a later stage,
`sorted()` cannot restore ordering the way Java's does, and the flag's single
consumer — `find_first()` — then hands back an arbitrary element of a sorted
pipeline:

```
.parallel().sorted(asc).find_first()              ->  1 1 1 1 1 1   (correct)
.parallel().unordered().sorted(asc).find_first()  ->  2 4 4 2 3 4
.parallel().sorted(asc).unordered().find_first()  ->  2 4 4 3       (identical: global)
```

Java returns the minimum in all three.

## What Changes

- **BREAKING** `unordered()` becomes a real queued `Op` — an identity sink
  carrying a `NOT_ORDERED` flag, mirroring Java's `StatelessOp` with an
  identity `opWrapSink`. It therefore derives-and-consumes like the other
  intermediate operations instead of mutating and returning `self`.
- `is_ordered()` becomes chain-derived: fold the queued ops' ordering flags
  left to right instead of reading an instance field. `_ordered` is removed
  from `Stream.__init__` and from `_derive()`'s copy list.
- `sorted()`'s `Op` carries an `IS_ORDERED` flag, so ordering is restored
  downstream of a sort exactly as in Java's `SortedOps`.
- **BREAKING** `find_first()` drops its `is_ordered()` short-circuit to
  `find_any()` and always drives under `SEQUENTIAL`. This matches HotSpot:
  `FindOp.mustFindFirst` is fixed when the op is constructed and never
  consults upstream `ORDERED`, so Java's `findFirst()` returns the leftmost
  element even on an unordered parallel stream.
- `for_each_ordered()` stops unconditionally forcing `SEQUENTIAL` and instead
  runs under the stream's own executor when the folded chain is unordered —
  the one place Java *does* branch on the flag for this terminal
  (`ForEachOps.OfRef.evaluateParallel` picks `ForEachOrderedTask` vs.
  `ForEachTask` on `StreamOpFlag.ORDERED.isKnown(...)`).
- `.parallel()` / `.sequential()` keep their current position-independent
  behaviour, unchanged. The ordering flag simply stops riding along on
  `_derive()` because it now lives in the chain.

## Capabilities

### New Capabilities

None. This reshapes existing behaviour rather than adding surface.

### Modified Capabilities

- `stream-ordering`: ordering becomes a positional characteristic derived from
  the queued chain rather than a per-instance flag; `unordered()` stops
  returning `self`; `sorted()` restores ordering downstream. The capability's
  current claim that the flag is "purely a declarative marker" that "does not
  itself alter iteration order" is retired — it stopped being true when
  `find_first()` began consuming it.
- `stream-find-first`: the requirement that `find_first()` may behave like
  `find_any()` when `is_ordered()` is `False` is removed; `find_first()` always
  returns the first element in encounter order.
- `stream-foreach-ordered`: a new requirement that `for_each_ordered()` on an
  unordered pipeline is released from the encounter-order guarantee and runs
  under the stream's own executor.
- `pipeline-immutability`: `unordered()` joins the enumerated intermediate
  operations that return a new instance and invalidate the receiver.

## Impact

- `src/snakestream/stream.py` — `unordered()`, `is_ordered()`, `__init__`,
  `_derive()`, `find_first()`, `for_each_ordered()`.
- `src/snakestream/ops.py` — a new identity op for `unordered()`; an ordering
  flag on `Op` (default: preserves upstream), set to clear on the new op and to
  restore on `_SortedOp`.
- `tests/test_unordered.py` — the return-`self` and survives-mode-switch tests
  are rewritten; positional and `sorted()`-restores tests are added.
  `tests/test_find_first.py` — the unordered-races test is retired.
  `tests/test_for_each_ordered.py` — an unordered-degrades test is added.
- `README.md` — the `unordered()`, `find_first()` and `for_each_ordered()`
  parity rows, plus a migration-log entry for the two breaking changes.
- No new dependencies. No change to `execution.py`'s executors or primitives.
