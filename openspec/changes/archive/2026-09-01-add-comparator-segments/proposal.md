## Why

Three rows in README's `java.util.Comparator` table are open on the same
premise: `then_comparing(comparator)` (never addressed either way),
`comparing(f, keyComparator)` and `thenComparing(f, keyComparator)` (both
recorded as decided against). All three say the same thing in Java — *compare
with a supplied `Comparator` rather than with natural ordering* — and the
reason they are open is one shared decision nobody has taken.

The origin of the decline (`openspec/changes/archive/2026-08-28-add-comparator-chaining/design.md`,
"`then_comparing()` takes a key extractor or another `KeyComparator`, and
nothing else") gives it plainly:

> refusing arbitrary two-argument comparators is what keeps "every segment
> yields a key" a total invariant. With it, `sort()` never has to fall back
> from the fast path, `_Descending` always applies, and there is no case where
> a sync comparator segment can be folded into the tuple via `cmp_to_key`
> while an async one cannot. Accepting the overload would introduce exactly
> that asymmetry, and Python cannot reliably tell a one-argument callable from
> a two-argument one anyway.

Both halves of that are weaker than they read, and this change is what closes
them:

- **The asymmetry is real but one-sided, and can be closed by refusing one
  side.** `cmp_to_key` turns a *sync* comparator into a key, so a sync
  comparator segment folds into the existing decorate-sort-undecorate tuple
  and rides every direction and null lane unchanged. An *async* one cannot —
  tuple comparison runs in C and cannot await. Rejecting an async comparator
  segment at construction restores the invariant in full rather than trading
  it away.
- **The disambiguation problem is narrower than stated.** `inspect.signature`
  resolves arity correctly for plain functions, lambdas, bound methods,
  callable objects, `functools.partial`, `operator.attrgetter` and C builtins;
  only `*args` is genuinely ambiguous, and defaulting that to *key extractor*
  keeps every call that works today meaning exactly what it means today.

Doing the three rows together is the point. Split up, each one re-argues the
same premise and two of them would keep citing a decline whose reason has
moved.

## What Changes

- **`then_comparing(comparator)`** — a bare two-argument `Comparator` is
  accepted as a tie-break segment, alongside today's key extractor and
  `KeyComparator`. Which one was passed is decided by parameter arity at
  construction.
- **`comparing(key_extractor, key_comparator)`** — a second, optional
  positional parameter supplying the ordering for the extracted keys, matching
  Java's two-argument `Comparator.comparing`. Re-decided, from declined to
  implemented.
- **`then_comparing(key_extractor, key_comparator)`** — the same for a
  tie-break segment, matching Java's two-argument `Comparator.thenComparing`.
  Re-decided, from declined to implemented.
- **An async comparator is rejected where a comparator segment is being
  built**, at construction, with an error naming the two supported
  alternatives (an async *key extractor* segment, or a bare async comparator
  passed straight to `sorted()`). A rejection, not a silent fallback: falling
  back to `merge_sort` would downgrade every *other* segment in the chain from
  the concurrent per-column gather that key-based ordering exists for, which
  is a silent O(n) → O(n log n) cliff in awaits.
- **Only the comparator must be sync.** `comparing(async_f, sync_c)` is
  supported: the extractor's keys are gathered concurrently as ever, and the
  comparator orders the resulting column.
- **A `nulls_first`/`nulls_last`-wrapped comparator passed to
  `then_comparing()` starts working.** It is a two-argument callable, so today
  it is silently taken for a key extractor and dies at call time with a
  `TypeError` about argument count; arity dispatch reads it correctly.
- Not breaking. Every existing call site keeps its present meaning; the
  widened parameter and the new second parameter are both additive.

## Capabilities

### New Capabilities

- `comparator-key-comparator`: an ordering may be supplied as a `Comparator`
  wherever the library would otherwise use natural ordering on a key — as a
  bare tie-break segment, or as the ordering applied to an extracted key.
  Covers how the callable is disambiguated from a key extractor, which
  comparators are refused and why, and how a comparator segment behaves under
  reversal, null tolerance, stability, and the direct-comparison path.

### Modified Capabilities

- `comparator-comparing`: `comparing()` gains an optional second parameter, so
  the requirement that it builds an ordering from a key extractor alone no
  longer states the whole surface.
- `comparator-chaining`: `then_comparing()`'s accepted argument widens from
  "a key extractor or another `KeyComparator`" to include a bare `Comparator`,
  and the method gains a two-argument form.

## Impact

- `src/snakestream/comparator.py` — `comparing()` gains a parameter;
  `KeyComparator.then_comparing()` widens and gains a two-argument form; the
  `Segment` alias becomes a tagged union; `__call__`'s two comparison paths
  learn to invoke a comparator segment directly rather than through a key.
- `src/snakestream/sort.py` — `_column()` (or its caller) builds
  `cmp_to_key(_checked(c))` for a comparator segment. The raw comparator is
  what `comparator.py` stores, so `_checked` stays in `sort.py` and the
  import edge established by `split-sort-into-comparator-and-sort` is
  unchanged.
- `src/snakestream/type.py` — the alias for a comparator segment, if one is
  needed, belongs here rather than inline.
- `README.md` — three rows move (one from "not yet implemented", two from
  struck-through/declined to implemented), and the `comparing`/
  `then_comparing` rows restate their signatures. No Migration entry: nothing
  breaks.
- `roadmap.md` — the **Later** row for this item is removed on archive.
- No change to `min()`, `max()`, `min_by()`, `max_by()`, `sorted()` or any
  executor. `KeyComparator` and `segments` have no consumers outside
  `comparator.py` and `sort.py`, so the blast radius is those two modules.
