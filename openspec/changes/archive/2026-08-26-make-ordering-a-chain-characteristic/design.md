## Context

See `proposal.md` for motivation. The constraints that shape the approach:

- A `Stream` holds four things: `_source`, `_chain`, `_executor`, `_consumed`
  — plus `_ordered`, the odd one out this change removes. Everything about
  *what* a pipeline does already lives in `_chain`; `_ordered` is the single
  piece of pipeline semantics that does not.
- `Op` (`sink.py:52`) is the chain element: it carries the user's arguments and
  builds a `Sink` via `link(downstream)`, once per sink chain. It has exactly
  one existing piece of protocol beyond `link()` — `make_shared_state()`,
  defaulting to `None` for stateless ops. Ordering is a second such
  characteristic and fits the same shape.
- `RACING` builds one sink chain per branch from the same `Op` list, so
  anything an `Op` declares must be a property of the op, not of a branch.
- Only two sites consult ordering today: `find_first()` (`stream.py:342`) and
  the public `is_ordered()`. `for_each_ordered()` ignores it entirely and
  always forces `SEQUENTIAL`.

Java's encoding, for reference — `StreamOpFlag` packs each characteristic as
two bits per flag with three meanings, SET / CLEAR / PRESERVE, and
`combineOpFlags(opFlags, previousStage.combinedFlags)` folds them left to
right down the stage list. `unordered()` is a `StatelessOp` contributing
`NOT_ORDERED` whose `opWrapSink` returns the downstream sink unchanged;
`sorted()` contributes `IS_ORDERED | IS_SORTED`.

## Goals / Non-Goals

**Goals:**

- Make ordering positional by making it a property of chain elements, with the
  chain as the only source of truth.
- Port Java's three-valued fold (SET / CLEAR / PRESERVE), not a bit-packed
  flag word.
- Keep `.parallel()` / `.sequential()` position-independent and untouched. The
  asymmetry between the two methods is the thing being restored, not removed.

**Non-Goals:**

- Exploiting unorderedness for speed in `limit`, `skip` or `distinct` under
  `RACING`. Java does (`SliceOps`, `DistinctOps`), and this change makes that
  possible by giving those ops a reliable answer to "is my upstream ordered",
  but each needs its own racing-branch coordination work and belongs in a
  separate change.
- Generalising `Op` into a multi-flag characteristics word. There is one
  characteristic; `SIZED`, `SORTED`, `DISTINCT` and `SHORT_CIRCUIT` are not
  being introduced speculatively.
- Fixing `.parallel().sorted()`'s branch-local sorting, which is a pre-existing
  `RACING` limitation unrelated to ordering bookkeeping.

## Decisions

### Ordering is a three-valued class attribute on `Op`, not a bitmask

```python
class Ordering(Enum):
    PRESERVE = auto()  # inherit upstream — the default, every existing op
    CLEAR = auto()  # _UnorderedOp
    SET = auto()  # _SortedOp


class Op(ABC):
    ordering: ClassVar[Ordering] = Ordering.PRESERVE
```

A `ClassVar` rather than instance state: ordering is a property of the
*operation*, not of the arguments the user passed to it, so `_SortedOp` sets it
once for every sort in every pipeline. This mirrors `make_shared_state()`'s
existing shape — a piece of `Op` protocol with a default that all but a
handful of ops accept.

*Alternative considered:* Java's packed `int` of two-bit fields. Rejected —
Java packs bits because it carries five flags through a hot combine on every
stage; we carry one, and a bitmask would trade a self-describing enum for
arithmetic that says nothing. Java's *semantics* are worth porting exactly; its
*encoding* is an optimisation for a problem this library does not have.

*Alternative considered:* a boolean `preserves_order`. Rejected — it cannot
express `sorted()`, which needs to *restore* ordering, not merely preserve it.
Two booleans would be the bitmask again with worse names.

### `Ordering` lives in `sink.py`, beside `Op`

It is part of the `Op` protocol, so it belongs with `Op`, `StatelessOp` and
`StatefulOp`. `type.py` is deliberately not the home: it holds
functional-interface aliases for *user-supplied callables* (`Predicate`,
`Mapper`, `Comparator`, …), and `Ordering` is neither a callable nor
user-supplied.

### `is_ordered()` folds the chain; `_ordered` is deleted

```python
def is_ordered(self) -> bool:
    ordered = True
    for op in self._chain:
        if op.ordering is not Ordering.PRESERVE:
            ordered = op.ordering is Ordering.SET
    return ordered
```

`_ordered` disappears from `__init__` and from `_derive()`'s copy list. The
chain becomes the sole source of truth, which is what makes the drift being
fixed here structurally impossible to reintroduce.

*Alternative considered:* keep `_ordered` as a field but update it
incrementally in `_extend()` from the op being appended, leaving
`_derive_executor()` to copy it unchanged. This is O(1) per query instead of
O(len(chain)), and — because the chain only ever grows by append — is exactly
equivalent to the fold. Rejected anyway: it reintroduces a denormalised copy
that every future derive path must remember to maintain, which is the precise
failure mode this change exists to remove. The fold runs at most once per
terminal over a chain of single digits; the cost is not measurable, and this is
not one of the per-element paths where the roadmap's benchmarks have mattered.

### `_UnorderedOp` links to nothing

```python
class _UnorderedOp(Op):
    ordering = Ordering.CLEAR

    def link(self, downstream: Sink[Any]) -> Sink[Any]:
        return downstream
```

No sink class, no wrapper, no per-element cost — `link()` returns the
downstream sink untouched, exactly as Java's `opWrapSink(flags, sink) { return
sink; }` does. It subclasses `Op` directly rather than `StatelessOp`, since it
has no arguments and no `_sink_cls`. The op exists purely to occupy a position
in the chain and declare a characteristic, which is precisely what makes
ordering positional.

### `unordered()` derives and consumes, like the other intermediate ops

```python
def unordered(self) -> Stream[T]:
    return self._extend(_UnorderedOp())
```

This is a **BREAKING** change to a method that currently mutates and returns
`self`. It is also the point: `unordered()` was only exempt from
`pipeline-immutability` because it had no chain element to append, and it had
no chain element because ordering was a field. Once ordering is in the chain,
the exemption has nothing left to justify it, and `unordered()` becomes the
ninth entry in that spec's enumerated list rather than a footnote against it.
`on_close()` remains exempt — it is a lifecycle method, not a pipeline stage.

### `find_first()` always drives `SEQUENTIAL`

The `is_ordered()` short-circuit to `find_any()` is deleted. Java does not do
this: `FindOp.mustFindFirst` is fixed when the op is constructed, and
`FindTask.onCompletion` performs its leftmost scan whenever that flag is set,
never consulting the upstream `ORDERED` flag. The javadoc *permits* returning
any element from an unordered stream; HotSpot declines to. Since the project's
first priority is 1:1 behaviour with the Java surface, we decline too.

The practical effect is that the wrong answer in the proposal's table stops
being reachable by any route, including routes `sorted()`-restoration would not
have covered — for example `.unordered().map(f).find_first()`.

*Alternative considered:* keep the degradation but make it positional, so that
`sorted()`'s restoration fixes the wrong answer. Rejected: it defends the
correctness of `sorted()` pipelines only, leaves `find_first()` diverging from
Java everywhere else, and buys nothing measurable — the racing path it selects
is not faster in any benchmarked case, it is merely permitted to be sloppier.

### `for_each_ordered()` becomes the flag's consumer

```python
async def for_each_ordered(self, consumer: Consumer[T]) -> None:
    executor = None if not self.is_ordered() else SEQUENTIAL
    return await self._evaluate(_ForEachSink(consumer), executor)
```

`_evaluate(sink, None)` already means "use the stream's own executor", so the
unordered case needs no new machinery. This is the one terminal where Java
genuinely branches on the flag —
`ForEachOps.OfRef.evaluateParallel` picks `ForEachOrderedTask` or `ForEachTask`
on `StreamOpFlag.ORDERED.isKnown(helper.getStreamAndOpFlags())` — and it
resolves the note left in `roadmap.md` that `for_each_ordered()` does not
consume the flag because `unordered()` "doesn't currently model" streams
without a defined encounter order. After this change it does model exactly
that.

Net readers of ordering after the change: `for_each_ordered()` and the public
`is_ordered()`. `find_first()` stops being one.

## Risks / Trade-offs

- [`unordered()` no longer returning `self` breaks any caller that binds it to
  a name and reuses the receiver] → Pre-1.0, and the fluent form
  `Stream.of(x).unordered().filter(...)` — the only form in the README, the
  tests and the docstrings — is unaffected. Reuse of the receiver now raises
  `IllegalStateException` loudly rather than failing silently. Record it in
  README's migration log alongside the other pre-1.0 renames.
- [`find_first()` no longer racing on an unordered parallel stream is a
  behaviour change, and a slower one in the case where the source is huge and
  the caller genuinely did not care which element came back] → Deliberate; it
  is the Java behaviour and the safe direction (a correct answer, more slowly).
  A caller who wants the race has `find_any()`, which is what Java tells them
  to use too.
- [`sorted()` restoring ordering will surprise anyone who reads `unordered()`
  as sticky for the rest of the pipeline] → It is Java's behaviour and the
  direct consequence of positionality; document it in the `unordered()` and
  `sorted()` README rows and cover it with a spec scenario so the intent is
  recorded rather than inferred.
- [Chain-folding makes `is_ordered()` O(len(chain)) where it was O(1)] →
  Chains are single-digit and the call happens at most once per terminal. See
  the alternative recorded above; the O(1) form is a one-line change if a
  benchmark ever justifies it.
- [Three ops now carry an `ordering` other than the default only implicitly,
  by inheriting `PRESERVE`] → That is the correct default for every existing
  op (`filter`, `map`, `flat_map`, `peek`, `distinct`, `limit`, `skip` all
  preserve upstream ordering in Java too), and stating it once on `Op` rather
  than eight times is the point of the `ClassVar`.

## Migration Plan

Single change, no staged rollout. The two breaking behaviours (`unordered()`'s
return, `find_first()`'s unordered case) land together, since separating them
would leave a release where the flag is positional but its only consumer reads
it in a way we intend to delete. Rollback is a straight revert — nothing here
is persisted or externally observable beyond the API surface.
