## Why

`find_first()` is the only terminal in the library that discards the caller's
declared execution mode:

```python
return await self._evaluate(_FindSink(), True, SEQUENTIAL)  # stream.py:561
```

```
  s.parallel().filter(slow).find_first()
            ^                     ^
    caller asks to race    terminal silently drops it; is_parallel() still True
```

Java's `findFirst()` is not a mode switch. `FindOp.mustFindFirst` is fixed when
the operation is constructed and `FindTask` still forks — it does a leftmost
scan *across branches*, it does not fall back to a sequential traversal. The
guarantee "the first element in encounter order" and the mechanism "run the
whole pipeline single-flight" were only ever fused here because, before
`order-racing-delivery` (2026-08-28), there was no other way to get encounter
order out of a racing pipeline. There is now, and it is the same barrier every
other order-observing terminal already uses.

**The guarantee does not change.** The barrier restores encounter order on any
chain, because `_guarded()` assigns the source index under the lock before
anything downstream can have an opinion — `unordered()` clears the ordering
*requirement*, never the *ability*. So `find_first()` still returns the true
leftmost element on an unordered parallel stream, and `stream-find-first`'s
headline requirement survives verbatim. Only its mechanism sentence moves.

Measured (Python 3.14.5, N=200, 4 workers, 10ms per element, best of 5; the
"after" column is `anext(iterator())`, which declares `observes_order=True` and
so runs the real delivery barrier through the real machinery, not a mock —
every row asserts both sides return the same element):

```
                       sequential (today)        barrier (after)     speedup
  map(10ms)             10.5 ms   1 call       10.9 ms   4 calls      0.96x
  filter(10ms, >=12)   133.4 ms  13 calls      42.9 ms  16 calls      3.11x
  flat_map(10ms, >=12) 137.8 ms  13 calls      42.9 ms  16 calls      3.21x
```

**No shape is slower.** The roadmap's caveat — that racing buys nothing where
the head cannot *drop* elements — is confirmed, but it costs nothing either:
the speculative maps run concurrently with the one that matters, not in front
of it. The shapes where the head drops run 3.1x, against a 4-worker ceiling.

## What Changes

- **`find_first()` stops naming `SEQUENTIAL`** and becomes a one-liner like
  every other terminal, demanding encounter order unconditionally rather than
  demanding sequential execution.
- **`observes_order` widens from a bool to a three-valued demand.** This is the
  only new machinery, and it makes clause 3 of `_split_point()` the same shape
  as clauses 1 and 2, one level up:

  ```
                      unconditional            conditional on is_ordered()
  op in the chain     Ordering.SET             order_sensitive
                      sorted()                 limit / skip / distinct
  ------------------------------------------------------------------------
  the terminal        ALWAYS                   IF_ORDERED
                      find_first()             reduce, to_array, collect,
                                               iterator, for_each_ordered
  ```

  ```python
  if demand is ALWAYS or (demand is IF_ORDERED and is_ordered(chain, initial=ordered_in)):
      return len(chain)
  ```

  No parameter is added anywhere: the value already threads through
  `Executor.value()` / `elements()` into `race_through()` and its recursion.
  `ALWAYS` propagating across a split is correct rather than merely harmless —
  `.parallel().sorted(c).unordered().map(f).find_first()` splits again at
  delivery, which is what "find_first never relaxes" means.
- **`_evaluate()`'s `executor` parameter is removed.** With
  `collapse-for-each-ordered-onto-barrier` landed, `find_first()` is its last
  caller. Note the roadmap's "what disappears" list is wrong on its other two
  entries: `Stream._is_ordered()` stays (`Stream.concat()` calls it at
  `stream.py:402`) and so does the `SEQUENTIAL` name in `stream.py`
  (`concat()` names it on the line above).
- **BREAKING (behavioural): `find_first()` no longer overrides `unordered()`.**
  An order-sensitive op on an unordered chain already races and already answers
  arbitrarily under every other terminal; `find_first()` was suppressing that
  permission for the whole pipeline:

  ```
  .unordered().limit(8).count()        limit races, subset arbitrary   <- spec'd today
  .unordered().limit(8).find_first()   limit deterministic             <- only because
                                                                          find_first
                                                                          forced SEQUENTIAL
  ```

  After this change the two agree. `find_first()` still returns the leftmost
  element *of what `limit` produced*; what became arbitrary is `limit`'s subset,
  not `find_first()`'s selection from it. README migration-log entry.
- **BREAKING (behavioural): a side-effecting callable in a non-dropping head may
  run more than once.** Sequential `find_first()` pulls exactly one element. The
  barrier version stops at the first *released group*, so the bound has two
  regimes, and the roadmap's flat "wastes <=15 maps" states neither:

  ```
  uniform latency      PROCESSES   (4)    branches are one group ahead at most
  slow head element    _READ_AHEAD (16)   branches keep pulling while index 0 is outstanding
  ```

  Measured worst case — `map()`, element 0 at 50ms, the rest at 1ms:

  ```
    sequential (today)   50.6 ms    1 map call
    barrier (after)      51.4 ms   16 map calls      wall clock 0.98x
  ```

  Wall-clock parity, 16x the work. README migration-log entry, since a mapper
  with side effects is where a caller notices.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `stream-find-first`: the guarantee is unchanged; the sentence "It SHALL
  achieve this by naming the sequential executor explicitly for that drive" is
  replaced by an unconditional encounter-order demand at delivery. **One
  scenario genuinely breaks** — "only the first element is pulled from upstream
  before the method returns" is true today only because `SEQUENTIAL` is forced.
  It is scoped to sequential streams and given a parallel counterpart bounded by
  the read-ahead window. The two parallel scenarios keep their THENs and lose
  their because-clauses. "There SHALL be exactly one implementation, with no
  branch on the stream's type, executor or ordering characteristic" survives and
  is strengthened.
- `stream-execution-model`: the requirement "A terminal uses the stream's
  executor unless it names one, and find_first() always names one" loses its
  second half; no terminal names an executor any more. Its two `find_first`
  scenarios keep their returned-element assertions and drop "the chain is driven
  under the sequential executor". The terminal's declaration widens from a bool
  to the three-valued demand, and `find_first()` is spec'd as its sole
  unconditional user.
- `racing-encounter-order`: the exemption "`find_first()` and
  `for_each_ordered()` are unaffected" is removed entirely (the previous change
  removes the other half). `find_first()` joins the terminals that observe
  encounter order, as the one that observes it unconditionally. `_split_point()`
  clause 3's gating is respecified against the three-valued demand.
- `terminal-sinks`: the requirement "An ordered drive is available regardless of
  stream mode" is removed — it has no users left. Its scenario "An unordered
  parallel `find_first()` still races ... behaves as `find_any()` does" is
  **already wrong today**: it contradicts `stream-find-first` and the shipped
  implementation, and was missed when `order-stateful-ops-under-racing`
  corrected the same stale rule in `stream-execution-model`. Deleting the
  requirement resolves the contradiction rather than papering over it.

## Impact

- `src/snakestream/stream.py`: `find_first()` becomes one line; `_evaluate()`
  loses its `executor` parameter; every terminal's `observes_order` argument
  becomes a demand value.
- `src/snakestream/execution.py`: `_split_point()`'s third clause; the demand
  type's definition and its threading through `Executor.value()` / `elements()`,
  `race_through()` and `_run_ordered_tail()`.
- `src/snakestream/collector.py` / `collectors.py`: `collect(collector)` maps the
  `UNORDERED` characteristic onto the demand instead of onto a bool.
- `README.md`: two migration-log entries (the `unordered()` override, and
  repeated invocation of a side-effecting head callable).
- Tests: the `find_first` scenarios above; new coverage for the two speculation
  regimes and for `ALWAYS` surviving a split.
- **Feeds roadmap item 3.** `_READ_AHEAD` now bounds a third thing, and it is
  the first one a caller can observe other than memory and latency: how many
  times their callable runs. That sharpens the export case and complicates the
  rename — it is now neither read-ahead nor a delivery buffer, but the window.
- **Depends on `collapse-for-each-ordered-onto-barrier`** for the `_evaluate()`
  parameter removal and for the `terminal-sinks` requirement to have one user
  left to delete.
