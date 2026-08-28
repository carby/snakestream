## Context

See proposal.md — Why. The mechanism this design extends is small and already in
place: `comparing()` returns an object rather than a closure precisely so
`sort()` can reach inside it, and `sort()` recognizes it by type and calls
`_sort_by_key()`, which decorates, sorts on the key alone, and undecorates.
`_KeyComparator` is referenced nowhere outside `comparator.py` and `sort.py`,
and `comparing` is imported from `snakestream.comparator` rather than
re-exported at the top level, so the surface being changed is narrow.

Two existing properties constrain everything below. Sorting on the key alone —
`list.sort(key=...)` over paired data rather than a bare tuple sort — is what
gives encounter order for equal keys for free, with no tie-break index; that
must survive. And callable classification is per-callable-per-composition
(`callable-dispatch`), decided once rather than per element, with a one-time
`isawaitable` trial as the safety net for a plain `def __call__` returning a
coroutine; each segment is a separate callable and so classifies separately.

## Goals / Non-Goals

**Goals:**

- Generalize the existing fast path from one key to k keys without adding a
  second sort pass, and without changing the k=1 path's measured cost.
- Keep the "every segment yields a key" invariant total, so the fast path can
  never be lost at runtime.
- Make the concurrency across segments real, not incidental — it is the
  capability's main justification over a hand-written tuple key.

**Non-Goals:**

- See proposal.md's out-of-scope list. At design level, additionally: no attempt
  to make `sort()` lazy about later keys. Deciding a key is unneeded would
  require knowing in advance that no pair ties on the earlier keys, which costs
  a pass to discover; eagerness is the price of the single-pass design and is
  spec'd rather than hidden.

## Decisions

### Segments are `(key_extractor, descending)` pairs, and direction is a flag, not a wrapper type

`KeyComparator` holds `tuple[tuple[KeyExtractor, bool], ...]`. `comparing(f)`
builds one ascending segment; `then_comparing(g)` appends; `reversed()` maps
`not` over every flag.

Alternative considered: represent reversal by wrapping the whole comparator in a
`_ReversedComparator` that negates `__call__`. Rejected — it is opaque to
`sort()`, which would either lose the fast path entirely or have to unwrap an
arbitrary nesting of wrappers to recover the segment list. A flag per segment
keeps the whole ordering inspectable as flat data, which is what the fast path
needs.

That flags are per-segment is also what makes Java's two reversal cases fall out
rather than needing separate handling: reversing a lexicographic order is
reversing each of its components, so `reversed()` after chaining and `reversed()`
before it differ exactly as Java's do, with one implementation.

### The fast path sorts tuples, in three lanes

Tuple comparison is lexicographic and short-circuits on the first unequal
component, in C. That is precisely tie-break semantics, so k keys still cost one
Timsort pass.

```
all ascending   ->  sorted(paired, key=itemgetter(0))
all descending  ->  sorted(paired, key=itemgetter(0), reverse=True)
mixed           ->  wrap the descending columns, then sort ascending
```

The all-descending lane matters: CPython's `sort(reverse=True)` is stable in the
strong sense — equal elements keep their original relative order, it is not a
post-hoc list reversal — so it equals comparator negation exactly, ties
included. Only genuinely mixed directions pay for a wrapper, and only on the
columns that asked for one.

The wrapper is the standard recipe, needing only the two dunders tuple
comparison uses:

```python
class _Descending:
    __slots__ = ("key",)

    def __init__(self, key):
        self.key = key

    def __lt__(self, other):
        return other.key < self.key

    def __eq__(self, other):
        return other.key == self.key
```

Alternative considered: a stable multi-pass sort — sort by the least significant
key first, then the next, relying on stability to carry earlier passes through.
It handles per-segment direction and arbitrary comparator segments naturally,
but costs k Timsort passes instead of one and never short-circuits. Rejected:
the tuple sort is both faster and smaller, and per-segment direction — the only
thing multi-pass bought — is covered by `_Descending`.

Alternative considered: negating numeric keys instead of wrapping. Rejected —
works only for numbers, and silently produces a wrong order for strings and
dates rather than failing.

### `k == 1` keeps today's exact path

One ascending segment must not pay for tuple construction or an outer gather.
This is a branch taken once per sort, so it costs nothing measurable, and it
means `add-comparator-comparing`'s measured figures stand unchanged rather than
needing to be re-established.

### Columns are extracted by calling the existing per-column routine k times, concurrently

Today's `_sort_by_key` body already is the per-column extractor — classify,
gather or list-comprehend, with the one-time trial safety net. It becomes
`_column(extractor, arr) -> list`, and the chain calls
`asyncio.gather(*(_column(f, arr) for f, _ in segments))`.

Nested gathers do not serialize: the outer starts k column coroutines, each
awaiting n extractions, so k×n extractions are in flight at once. That is the
same concurrency a single flat gather over k×n awaitables would give, without
having to slice a flat result list back into columns — meaningfully simpler for
identical behaviour. A sync extractor's `_column` never awaits, so mixing costs
nothing.

Alternative considered: one flat gather with index arithmetic to re-split.
Rejected on readability for no concurrency gain.

### `__call__` walks segments lazily and stays sync when it can

The direct-call path negates the sign for a descending segment and returns at
the first non-zero. It stays a plain sync function when every segment is sync;
if any segment is async it must return a coroutine, because a later async
segment may be reached. Per-segment classification means a sync segment inside
an async chain is still not awaited.

Laziness here is the opposite of the sort path's eagerness, and deliberately so:
`min()`/`max()` compare a small number of pairs, so extracting per comparison is
cheaper than k×n eager extractions, and short-circuiting can skip an expensive
later key entirely. Both paths agree on order; they differ in invocation counts
and in which extractor errors are reachable. The specs state this rather than
leaving it to be discovered.

### `KeyComparator` becomes public so the methods are visible to `ty`

`comparing()` currently returns the `Comparator` alias, which is
`Callable[[T, T], int | Awaitable[int]]` and has no attributes; annotating a
chainable return as that alias would fail `ty check` at the first
`.then_comparing(...)`.

Alternatives considered: leak the private name into the signature
(`-> _KeyComparator`), or add a `Protocol` to `type.py`. The rename is the
smallest of the three and needs no new abstraction — the project is pre-1.0 and
the name was private with two in-repo references. `type.py` holds callable
aliases and protocols; `KeyComparator` is a concrete class, so it stays in
`comparator.py` beside `comparing()`.

`KeyComparator` must remain assignable to the `Comparator` alias at every call
site that accepts one (`sorted`, `min`, `max`, `min_by`, `max_by`). It already
satisfies that annotation today via `__call__`, so this is a check to run early
rather than an expected obstacle.

### `then_comparing()` takes a key extractor or another `KeyComparator`, and nothing else

Rationale is in proposal.md's out-of-scope list. The design consequence worth
recording: refusing arbitrary two-argument comparators is what keeps "every
segment yields a key" a total invariant. With it, `sort()` never has to fall
back from the fast path, `_Descending` always applies, and there is no case
where a sync comparator segment can be folded into the tuple via `cmp_to_key`
while an async one cannot. Accepting the overload would introduce exactly that
asymmetry, and Python cannot reliably tell a one-argument callable from a
two-argument one anyway.

## Risks / Trade-offs

- **The fast path and the `__call__` path could drift, giving different orders
  for the same chained comparator.** → The same risk `add-comparator-comparing`
  carried, now over more surface. Tests must assert the two agree for every
  shape: chained, reversed-before-chaining, reversed-after-chaining, and mixed
  directions, including on ties.
- **`_Descending` moves the mixed-direction comparison from C into Python
  dunders.** → Bounded: paid only on descending columns, only in a mixed chain,
  and only once earlier components tie. The all-ascending and all-descending
  lanes avoid it entirely, which covers the common cases. Worth measuring, not
  worth avoiding.
- **Eager extraction can invoke a side-effecting or expensive extractor for keys
  no comparison needs, and can raise where the lazy path would not.** → Spec'd
  as behaviour rather than mitigated. It is inherent to a single-pass tuple
  sort, and the alternative — lazily deciding a column is unnecessary — costs
  more than it saves.
- **`sorted(reverse=True)` and `reversed()` now compose, and mean different
  things.** → `reverse=True` reverses the buffer after sorting, flipping tied
  elements; `reversed()` negates the comparator, which does not. Stacking them
  is expressible and must be pinned by a test. This is a pre-existing asymmetry
  in `_SortedSink` that this change makes reachable in a new combination, not
  one it introduces; changing it is out of scope.
- **`reversed()` shadows nothing but reads like the builtin.** → It is a method
  on an object, never a bare name, and it is Java's name for exactly this
  operation, which is the project's stated naming rule.
- **Two new public names permanently on the pre-1.0 surface.** → Both are direct
  Java ports carrying Java's names, so the odds of wanting to rename them are
  low; `KeyComparator` is additionally a name users receive rather than
  construct.
- **The README's `reversed()` row currently justifies skipping it as "already
  covered by `sorted(comparator, reverse=True)`".** → That justification was
  always a slight overclaim (buffer reversal is not comparator negation) and
  becomes plainly wrong for a chain. The row moves to implemented; the
  `sorted()` row should note the distinction.

## Migration Plan

Purely additive apart from a rename of a previously-private class with two
in-repo references. No existing signature changes, no behaviour changes on any
existing path, nothing to deprecate. Every comparator that works today keeps
working on the same path, and `comparing(f)` with no chaining reaches exactly
the code it reaches now.

The README's `java.util.Comparator` table needs `thenComparing` and `reversed`
moved out of the struck-through "decided against" style into implemented rows,
the `keyComparator` overloads added as newly-recorded deliberate skips, and the
`comparing()` row's tuple-key note amended: a tuple key remains the better
answer for a sync multi-key ordering (one call per element, no wrapper object,
no gather), and chaining earns its keep for async extractors and for mixed
directions. That distinction should be stated as a rule with its reason, not as
a preference.
