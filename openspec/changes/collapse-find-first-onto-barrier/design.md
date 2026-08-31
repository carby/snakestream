## Context

See `proposal.md` — Why, which carries the motivation and the measurements.

Two facts about the current code shape the approach. First, `Executor`'s
docstring already argues that the order declaration belongs *on the protocol*
rather than being read off the terminal sink, "because `elements()` has no
terminal sink to read". That argument is untouched by this change; only the
declaration's type widens. Second, `_split_point()` already expresses two kinds
of ordering demand — unconditional (`Ordering.SET`) and conditional on the
pipeline being ordered at that position (`order_sensitive`) — but only for
*operations*. The terminal side has just one, and `find_first()` is the terminal
that needs the other.

This change lands **after** `collapse-for-each-ordered-onto-barrier`, which
leaves `find_first()` as the sole caller of `_evaluate()`'s `executor`
parameter and the sole user of the `terminal-sinks` ordered-drive requirement.
Both are removed here.

## Goals / Non-Goals

**Goals:**

- Express a terminal's ordering demand in the same vocabulary the op side
  already uses, so the two sides of `_split_point()` read as one idea.
- Remove the last place a terminal names an executor.

**Non-Goals:**

- Changing `find_first()`'s returned element, on any pipeline. The guarantee is
  restated, not relaxed; see the `stream-find-first` delta.
- Exporting the demand type. It is internal in the way `Ordering` is internal:
  a caller influences ordering through `unordered()` and `sorted()`, never by
  naming a demand.
- Touching `_READ_AHEAD`'s value, name or visibility. This change makes it bound
  a third thing and thereby strengthens roadmap item 3's case; the export and
  rename stay that item's work, not a line slipped into a behaviour break.
- Removing `Stream._is_ordered()` or `stream.py`'s `SEQUENTIAL` import.
  `Stream.concat()` keeps both.

## Decisions

### The declaration widens from `bool` to a three-valued demand

```python
class OrderDemand(Enum):
    NONE  # count, for_each, find_any, max, min, all/any/none_match
    IF_ORDERED  # reduce, to_array, collect(...), iterator, for_each_ordered
    ALWAYS  # find_first, and nothing else
```

and `_split_point()`'s third clause becomes the same shape as its first two:

```
                    unconditional          conditional on is_ordered()
op in the chain     Ordering.SET           order_sensitive
the terminal        OrderDemand.ALWAYS     OrderDemand.IF_ORDERED
```

```python
if demand is OrderDemand.ALWAYS or (demand is OrderDemand.IF_ORDERED and is_ordered(chain, initial=ordered_in)):
    return len(chain)
```

No parameter is added anywhere: the value threads through
`Executor.value()`/`elements()` into `race_through()` and its recursion on
exactly the path the bool already takes. `Sequential` continues to accept and
ignore it, with its existing comment intact — a single ordered pass delivers in
encounter order whether or not anyone is looking.

Call sites read as declarations rather than as flags, which is the point:

```python
await self._evaluate(_CountSink(), OrderDemand.NONE)
await self._evaluate(_ReduceSink(...), OrderDemand.IF_ORDERED)
await self._evaluate(_FindSink(), OrderDemand.ALWAYS)
```

The parameter is renamed `demand` at every hop. `observes_order=OrderDemand.NONE`
would read as a contradiction.

*Alternative: a trailing pseudo-op declaring `Ordering.SET`*, appended to the
chain for the drive so clause 1 fires unconditionally. This is what the roadmap
proposed, and `_UnorderedOp` is real precedent for a sink-less op. Rejected on
three counts. It nets zero deletions — `_evaluate()` trades `executor: Executor
| None` for `demand: Op | None`, which was the item's one remaining payoff. It
lands the split at index `n` rather than `len(chain)`, so `_run_ordered_tail()`
takes its `barrier, rest` path and runs an extra `stream_through()` layer over
the reordered stream, where clause 3's empty-tail case is documented as "the
reordered stream *is* the answer". And it misstates the thing: an op declares a
characteristic *at a position*, and this is a demand originating at the
terminal — precisely the distinction `order-racing-delivery` introduced
`observes_order` to draw. Putting the demand back into the chain undoes that.

*Alternative: a second bool* (`observes_order` plus `unconditional`). Two bools
admit four states of which one is meaningless (`observes_order=False,
unconditional=True`), and nothing in the type stops a terminal declaring it.

### `ALWAYS` propagates across a split, and that is load-bearing

`_run_ordered_tail()` passes the demand into its recursive `race_through()`. With
`ALWAYS` the resumed suffix splits at its own `len()` regardless of what the
suffix's ops did to the characteristic, so:

```
  .parallel().sorted(c).unordered().map(f).find_first()
              ^ splits here          ^ suffix races, then splits again at delivery
```

still returns the leftmost element. That is the correct reading of "find_first
never relaxes", and it falls out of the propagation rather than needing a special
case. A conditional demand in the same position is correctly released by the
`unordered()`, because `is_ordered()`'s `initial` seed carries the cleared
characteristic across the split.

### The enum lives in `execution.py`

`_split_point()` reads it and `Executor`'s protocol carries it; `stream.py`
already imports `SEQUENTIAL`, `RACING` and `PROCESSES` from there. It does not
belong in `sink.py` beside `Ordering` — `Ordering` is there because `Op` needs
it and `execution.py` may reach it, whereas nothing in `sink.py` has an opinion
about what a terminal demands. It is not a type alias, so `type.py` is not its
home either.

*Naming note:* Java has no counterpart to borrow. Its terminals answer this
question by choosing a task class (`FindTask` vs `ForEachTask`), so there is no
name to be close to, and an invented one is unavoidable. `OrderDemand` is built
to sit beside the vocabulary already here — `Ordering` says what an op does *to*
the characteristic, `OrderDemand` says what a terminal asks *of* it.

### `collect()` maps the collector's characteristic onto the demand

`Characteristics.UNORDERED not in collector.characteristics` becomes a choice
between `IF_ORDERED` and `NONE`. A collector can never produce `ALWAYS`: the
characteristic set says whether ordering matters to the result, which is exactly
a conditional demand. `find_first()` remains the only `ALWAYS` in the codebase,
and the `stream-execution-model` delta states that as a requirement so a future
terminal cannot pick it up unnoticed.

## Risks / Trade-offs

**A short-circuiting terminal behind the reorder barrier must not leak
branches** → `_FindSink` requests cancellation after one element, so `drain()`
stops pulling from `_release_in_order()`, whose `finally` cancels in-flight
`anext()` tasks, awaits them, and closes each branch so the shared source's own
`finally` runs. This path exists and is correct, but no short-circuiting
terminal has ever driven it — `find_first()` was sequential and `find_any()`
never splits. Needs an explicit test that a parallel `find_first()` over a slow
infinite source terminates and leaves no pending tasks.

**A degenerate `.parallel().find_first()` gets slower** → With an empty chain the
split is at 0, so four branches and a reorder barrier are spun up to return
element 0, where today `SEQUENTIAL` pulls one element. The absolute cost is
small and the shape is pathological (a parallel pipeline with no operations),
but it is a real regression and should be measured rather than assumed
negligible. If it is not negligible, the fix is a fast path on an empty chain,
not a retreat to naming `SEQUENTIAL`.

**Asserting the speculation bound is timing-dependent** → The proposal's two
regimes (`PROCESSES` under uniform latency, `_READ_AHEAD` under a slow head) are
measurements, not invariants; a loaded CI machine can land between them. Tests
SHALL assert the invariant — invocations `<= _READ_AHEAD`, and `> 1` on a
parallel stream with a deliberately slow head element — never the exact figure.
The `== 1` assertion is safe only on a sequential stream.

**A side-effecting chain callable now runs more than once** → README migration
entry, and the `stream-find-first` delta states the bound and names
`.sequential()` as the escape hatch. There is no mitigation beyond documenting
it: it is inherent to racing before the answer is known, and Java's `FindTask`
does the same speculative work in its leaves.

**`find_first()` stops making an unordered pipeline deterministic** → Second
README entry. The framing that matters is that `find_first()` was *suppressing*
a permission `unordered()` already grants everywhere else, so this removes an
inconsistency rather than adding nondeterminism; `.sequential()` restores the
old behaviour exactly.

## Migration Plan

Lands after `collapse-for-each-ordered-onto-barrier`, in one commit, with both
README migration-log entries in that same commit per project convention.
Rollback is a revert; nothing is persisted.

The bool-to-enum widening touches every terminal's call site in one mechanical
pass. `ty` catches a missed site only if the parameter is annotated
`OrderDemand` rather than left inferable, so the annotation on `_evaluate()`,
`Executor.value()`, `Executor.elements()`, `race_through()` and `_split_point()`
is what makes the sweep verifiable rather than eyeballed. Do it before removing
`_evaluate()`'s `executor` parameter, so the two mechanical edits fail
independently if either is wrong.
