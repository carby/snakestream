## Context

See `proposal.md` — **Why**. Three pieces of the existing module shape every
decision below:

- `reducing()` (`collectors.py:342`) already dispatches a Java overload set by
  **arity**: a three-entry `@overload` block for the type checker, `_UNSET`
  sentinel defaults, and one runtime branch that reassigns the positional
  arguments. Its case is harder than either of ours — position 1 is
  `binary_operator`, `identity`, or `identity` again depending on how many
  arguments arrive.
- `to_collection(collection_supplier)` already ships a caller-supplied
  container, and declares **no** characteristics.
- `_finish_groups()` is shared by `grouping_by()` and `partitioning_by()`, and
  today rebuilds its result as a plain `dict` in both the finisher and the
  no-finisher path.

## Goals / Non-Goals

**Goals:**

- Java's argument *positions*, not just its argument *set* — `map_factory`
  sits second in `grouping_by`, where Java puts `mapFactory`.
- One stated rule for what a caller-supplied container does to `UNORDERED`,
  shared with `to_collection()` rather than invented per factory.
- The caller's mapping type survives the finisher.

**Non-Goals:**

- Any change to `partitioning_by()`. Java's `partitioningBy` has no container
  argument — the two keys are fixed — and it must come through the shared
  finisher unaffected.
- Any change to `Collector`, `_CollectorSink`, or the racing delivery barrier.
  Two collectors change what they *declare* to the barrier; the barrier is
  untouched.
- Inferring whether a mapping type's equality is key-order-insensitive.

## Decisions

### 1. Arity dispatch, not keyword-only, for `grouping_by`

`grouping_by(f, to_set())` must keep binding `to_set()` to `downstream`, so
Java's `(classifier, mapFactory, downstream)` order looks like a positional
collision. It is not. The form is decided by **how many** arguments arrive, and
a two-argument call can only be the two-argument form:

```
  grouping_by(f)                        1 -> downstream=_TO_LIST, container=dict
  grouping_by(f, to_set())              2 -> arg2 is downstream    (unchanged)
  grouping_by(f, OrderedDict, to_set()) 3 -> arg2 is map_factory
```

Implemented as `reducing()` does it: `@overload` entries carrying
`# pragma: no cover`, `_UNSET` defaults, one arity branch that shifts the
positionals.

*Alternatives considered.* **Keyword-only `map_factory` after `downstream`** —
no collision, but diverges from Java's argument order for a problem arity
already solves, and this module has a precedent against it. **Runtime
`isinstance(arg2, Collector)` sniffing** — reproduces Java's static overload
resolution dynamically, and misbinds a hand-rolled `Collector`-lookalike; arity
needs no such judgement. **Breaking the two-argument call** — rejected outright;
nothing here justifies a migration entry.

### 2. `to_map` gets Java's three overloads and no fourth

`to_map`'s positions never shift, so its `@overload` block is a plain
three-entry set. The consequence worth stating is what it *excludes*:
`to_map(k, v, map_supplier)` is not a form, because Java has no such overload.

That is what keeps gap 2 free of the characteristics question. The four-argument
form always carries a `merge_function`, so it declares nothing for the reason
the three-argument form already declares nothing — a caller-supplied merge need
not commute — and the container never gets a turn to speak.

The exclusion is enforced by the declared type surface and `ty`, not by a
runtime raise. A runtime check would have to distinguish "a merge function" from
"a mapping type" by inspection, which is decision 1's rejected sniffing in
another costume, and there is no honest predicate for it: both are callables of
the right shape.

*Alternative considered.* **Accept `map_supplier` with `merge_function=None`**
as a Python convenience. Rejected: it expands the public surface past Java for
a caller who can pass a two-line merge, and it would drag the container
characteristics question into `to_map` where it otherwise does not arise.

### 3. A caller-supplied container clears `UNORDERED`, unconditionally

`grouping_by(f, map_factory, downstream)` declares nothing, whatever
`downstream` declares. The shipped derivation rests on `dict` equality ignoring
key insertion order; `OrderedDict.__eq__` against another `OrderedDict` does
not, and key insertion order here follows the order groups were first seen —
which racing reorders. Verified rather than assumed:

```
  OrderedDict([('a',1),('b',2)]) == OrderedDict([('b',2),('a',1)])  ->  False
  dict(...)                      == dict(...)                       ->  True
```

The rule keys on `map_factory` **being supplied at all**, not on the type it
produces — so `grouping_by(f, dict, to_set())` also declares nothing, even
though that container would allow the mark. A caller who reaches for the
three-argument form with a plain `dict` has written the two-argument form the
long way round, and the alternative is worse: deciding from the type means
either calling the factory at *construction* time to look at what it returns
(the factory is a per-collection supplier and must not be called early) or a
`map_factory is dict` special case, which is a hardcoded whitelist that answers
nothing for any other type.

`unordered()` at the pipeline is the escape hatch, as it is for
`to_map`-with-a-merge and for `to_collection()`.

### 4. `_finish_groups()` finishes in place, on both paths

For the caller's mapping type to survive, the finished values must be written
back into the mapping the factory produced, rather than collected into a new
`dict` — Java's `groupingBy` finisher does the same in-place replacement.

Both paths unify on that rather than branching. Today the no-finisher path
returns `dict(groups)`, a copy; in place it returns the box's own mapping. That
is not observable — `_GroupBox` is discarded at the end of the collection and
its mapping is shared with nothing — and it drops one copy per collection.
Iteration is over `list(groups)` rather than the mapping itself: rebinding an
existing key cannot resize a `dict`, but an arbitrary `MutableMapping` owes no
such guarantee, and the key list is one per group.

`partitioning_by()` passes no factory and keeps its `dict`; it reaches the same
in-place finisher with the same two keys it seeds in its supplier.

### 5. The supplier becomes async on both factories, with no fast path

`to_map`'s container comes from `_ToMapBox(await _maybe_await(map_supplier))`
instead of `field(default_factory=dict)`, and `grouping_by`'s from
`_GroupBox(await _maybe_await(map_factory))` instead of `_GroupBox({})`, with
`dict` as each default. Both suppliers become `async def` unconditionally.

A supplier runs **once per collection**, not per element, so the module's usual
reason for branching — the per-element path — does not apply, and one code path
is worth more than one coroutine per collect. `partitioning_by`'s supplier is
already `async def` for the same reason.

`map_supplier`/`map_factory` reuse the existing `Supplier` alias from
`type.py`. `_C` is bound to `_SupportsAdd` and is wrong here; a mapping
typevar bound to `MutableMapping` belongs in `type.py` beside it, not inline.

### 6. Java's own inconsistent parameter names are kept

Java names the argument `mapSupplier` on `toMap` and `mapFactory` on
`groupingBy`. Both are mirrored as-is (`map_supplier`, `map_factory`) rather
than unified. The 1:1 surface is the contract, and README's placeholder rows
already carry both names.

## Risks / Trade-offs

- **`grouping_by(f, dict, to_set())` is more pessimistic than
  `grouping_by(f, to_set())`** despite collecting an equal result → accepted,
  and it is the point of decision 3. The pessimism is one delivery barrier, the
  two calls are trivially interconvertible, and `unordered()` releases it.
- **Arity dispatch loses the argument names in the error a wrong-arity call
  produces** — the implementation signature is positional-with-sentinels, so a
  four-argument `grouping_by` reports against that rather than against an
  overload → mitigated by `@overload` making the wrong call a static error
  before it runs, which is the same trade `reducing()` already takes.
- **In-place finishing gives the two-argument `grouping_by` a different object
  identity** (the box's mapping, not a copy) → not observable; nothing else
  holds a reference to it. Covered by the existing scenarios either way.
- **A `map_factory` returning a non-empty mapping** produces a result holding
  keys no element classified into → out of scope, and identical to what
  `to_collection()` already does with a pre-filled container. The factory is
  specified to produce a fresh empty mapping.
- **Coverage gate (98%)**: `@overload` stubs are uncovered lines. Mitigated by
  the `# pragma: no cover` the existing `reducing()` overloads already carry.
