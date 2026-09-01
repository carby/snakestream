## Context

See proposal.md — Why, for the motivation and for the origin text this change
re-decides.

The constraints that shape the approach, all present in today's code:

- `KeyComparator` holds `segments: tuple[(KeyExtractor, bool), ...]` plus a
  whole-comparator `nulls: NullPlacement`. `sort.py` unwraps `segments` for the
  decorate-sort-undecorate fast path; `__call__` (`_compare_sync` /
  `_compare_async`) serves every consumer that does not know to look — `min()`,
  `max()`, `min_by()`, `max_by()`.
- `_sort_by_key()` builds one column per segment via `_column()`, gathering
  across elements and across columns, then sorts in one of three direction
  lanes (plain, `reverse=True`, `_Descending` wrappers) with an orthogonal
  `(present, key)` wrapping when the comparator is null-tolerant.
- `_checked()` — the wrapper that enforces the "no bool" contract under
  `cmp_to_key` — lives in `sort.py`, and `split-sort-into-comparator-and-sort`
  put it there deliberately. `comparator.py` does not import from `sort.py`.
- `callable-dispatch` classifies each callable sync/async once at construction
  via `is_async_callable`, with a one-time `isawaitable` trial as a safety net
  for a callable that lies (a plain `def __call__` returning a coroutine).
- `KeyComparator` and `segments` have no consumers outside `comparator.py` and
  `sort.py`.

Verified before writing this, on 2026-09-01, because the whole approach rests
on it: a `functools.cmp_to_key` object sorts correctly in all four places a
segment's key can land — plain ascending, under `reverse=True`, wrapped in
`_Descending`, and as the second component of a `(present, key)` tolerant
tuple — and supports `<` and `>` so `__call__`'s `(ka > kb) - (ka < kb)` works
on one too.

## Goals / Non-Goals

**Goals:**

- One mechanism serving all three README rows, so none of them is left citing a
  premise the others have moved.
- Keep "every segment yields a key" a total invariant at sort time. No fallback
  path out of `_sort_by_key()`, so `_Descending`, the three direction lanes and
  the tolerant column all continue to apply unconditionally.
- Keep the `comparator.py` → `sort.py` import direction and `_checked()`'s
  home unchanged.
- Cost nothing to a chain that uses no supplied comparator.

**Non-Goals:**

- Supporting an async comparator as a supplied ordering, by fallback or
  otherwise. Rejected here, deliberately reversibly — see Decision 2.
- Changing `sorted()`, `min()`, `max()`, `min_by()`, `max_by()`, `merge_sort()`,
  or any executor.
- Making `KeyComparator.__call__` as cheap as the sort fast path. It is the
  lazy, per-comparison path by construction and stays so.
- A public name for the "this callable is a comparator, not an extractor"
  distinction. Arity settles it — see Decision 4.

## Decisions

### Decision 1: A comparator segment stores the raw comparator, and `sort.py` builds the key

`Segment` becomes a tagged union: a segment carries either a key extractor or a
supplied comparator, alongside its existing `descending` flag. The supplied
comparator is stored **raw**. `sort.py` builds `cmp_to_key(_checked(c))` for it
when it builds that segment's column, and `KeyComparator.__call__` invokes it
**directly** as a comparator.

Two reasons the raw form is what gets stored.

*The module split.* `_checked()` is in `sort.py` and belongs there —
`split-sort-into-comparator-and-sort` decided that, and `then_comparing()` is
in `comparator.py`. Erasing to a key at construction would need
`comparator.py` to import `_checked`, reversing the import edge for one
wrapper.

*The direct-comparison path.* `min()`, `max()`, `min_by()` and `max_by()` never
see `segments`; they go through `__call__`. If a comparator segment were stored
already erased to `cmp_to_key(...)`, each comparison on that segment would
allocate two wrapper objects and invoke the user's comparator twice — once
inside each wrapper's `__lt__`/`__gt__` — to recover a sign the comparator
would have returned directly. Storing raw makes that path one call, which is
strictly better and is also the only shape in which the sign can be checked
once.

*Alternative considered — erase at construction to `(cmp_to_key(_checked(c)), descending)`.*
The minimal diff: `Segment`'s shape is untouched and `sort.py` needs no change
at all. Rejected on both counts above. The permanent cost to four terminals,
paid on every comparison, is not worth a smaller diff in a change that has to
touch `sort.py` for the async rejection's error path anyway.

### Decision 2: An async supplied comparator is rejected at construction, not fallen back from

Tuple comparison runs in C and cannot await, so an async comparator segment has
no key. Three shapes were considered.

*Chosen — reject at construction.* `then_comparing()` and `comparing()` raise
`StreamBuildException` when the callable in a comparator position is async.
The invariant stays total: no segment can exist that `_sort_by_key()` cannot
build a column for, so there is no fallback branch, `_Descending` still always
applies, and no lane acquires a precondition. The user has two supported
routes, both better shapes than the one refused: an async **key extractor**
segment (supported today, gathers concurrently, O(n) awaits), or a bare async
comparator passed straight to `sorted()`, which reaches `merge_sort()` as it
always has. The error names both.

*Rejected — whole-chain fallback to `merge_sort` over `__call__`.* Correct, and
`_compare_async` already has the loop shape. But a single async comparator
segment would silently downgrade **every other segment** in the chain from the
concurrent per-column gather to sequential awaits inside `merge_sort`'s inner
loop — for `comparing(async_f).then_comparing(async_c)`, `f` goes from n
gathered awaits to n log n serial ones. That is a silent O(n) → O(n log n)
cliff on the exact chain that key-based chaining exists to make fast, in a
library whose docstrings carry measured figures precisely so cliffs are not
silent.

*Rejected — split the chain at the comparator boundary.* Sort the prefix on the
fast path, group the runs of equal prefix keys, `merge_sort` each group with
the async comparator, recurse for the suffix. Genuinely correct and often
cheap, since the groups are small. Rejected as unmotivated machinery: no use
case has been raised, and it is strictly more complex than either alternative.

The ordering of these matters for reversibility. Rejecting leaves both
alternatives available as a later, deliberate, measured addition, and turning a
rejection into an acceptance is not a breaking change. Shipping the fallback
would bake the cliff into observable behaviour, and removing it later would be.

### Decision 3: `is_async_callable` at construction, with the existing trial as the net

`is_async_callable` is the classifier used everywhere else (`callable-dispatch`)
and is what the rejection tests. It does not catch a callable that lies — a
plain `def __call__` returning a coroutine — which is why the library carries
one-time `isawaitable` trials in `sort()` and `_column()`.

Such a comparator slips past construction and reaches `_checked()`, which sees
a coroutine, finds `type(sign) is not int`, and raises. The message it raises
today — "comparator must return an int" — is true but points at the wrong rule.
`_checked()` (or the comparator-segment wrapper built beside it) gains a
coroutine test on the raising path only, so the message names the async
rejection instead. The raising path is already off the hot path, so this costs
the sync fast path nothing.

*Alternative considered — a trial comparator invocation at construction.* It
would catch the liar early and give one uniform error site. Rejected: it
invokes a user comparator with no elements to invoke it on, and the existing
trials all sit where real data is already available.

### Decision 4: Arity disambiguates, with `*args` defaulting to key extractor

`then_comparing(other)` is the only genuinely ambiguous position — the
two-argument forms are unambiguous by signature, and a `KeyComparator` is
already caught by `isinstance` and keeps precedence. `inspect.signature` is
used to count positional parameters: one means key extractor, two means
comparator.

Measured against the real callable shapes on 2026-09-01, which is what makes
this viable rather than the origin's "Python cannot reliably tell":

| shape | resolves to |
|---|---|
| `lambda x: x`, `def one(x)` | 1 |
| `lambda a, b: ...`, `def two(a, b)` | 2 |
| callable object with `__call__(self, a, b)` | 2 |
| the value `nulls_first(cmp)` returns | 2 |
| `functools.partial(two, 1)` | 1 |
| `operator.attrgetter("x")` | 1 |
| `str.lower`, `len` (C builtins) | 1 |
| `functools.cmp_to_key(two)` | 1 |
| `def starred(*a)` | indeterminate |

Every realistic shape answers correctly, including the C builtins and callable
objects the origin doubted. Only `*args` is indeterminate, and it defaults to
**key extractor** — the meaning such a callable already carries today, so no
call that works now can change meaning. A misclassification in either direction
raises `TypeError` on argument count at the first element rather than silently
producing a wrong order, which is what makes a signature-based rule acceptable
here where it would not be for a rule whose failure reorders silently.

*Alternative considered — a distinct method name for the comparator form.*
Unambiguous, but puts a non-Java name on the public surface, against the
project's stated naming rule, and does not help the two-argument rows at all.

*Alternative considered — an explicit wrapper the caller applies.* Also
unambiguous, at the cost of a new public name and a wrapper at every call site
Java requires nothing at. Worth revisiting only if arity dispatch proves
insufficient in practice.

### Decision 5: Null tolerance and reversal need no new rules

Both fall out of where a comparator segment sits.

`_column()` never invokes anything on a `None` element — it yields `None`
directly — so a null element presents as a null key on a comparator segment
exactly as on an extractor segment, and `_tolerant_column()` places it. A
comparator segment has no *extracted key*, so the null-key case simply does not
arise for it; only the null-element case does, and it is already covered.

`reversed()` flips each segment's `descending` flag, and a `cmp_to_key` object
was verified to sort correctly under both `reverse=True` and `_Descending`. So
negating a supplied ordering is the same operation as negating any other, and
the "flip every component" identity that makes reverse-before-chaining and
reverse-after-chaining differ correctly is preserved.

### Decision 6: The two-argument forms compile to a comparator segment

`comparing(f, c)` and `then_comparing(f, c)` are not a fourth segment kind.
Both mean "order elements by applying `c` to `f`'s keys", which is the
comparator segment `lambda a, b: c(f(a), f(b))` — so they lower onto Decision
1's machinery with no new lane, no new column type, and no new spec surface
beyond the requirement that says so.

One consequence worth stating, because it is the reason `comparing(async_f, c)`
works: `f` is still extracted per element into a column, and `c` orders that
column. The extractor keeps its gather; only `c` is constrained to sync. The
alias for whatever type carries an extractor-plus-comparator pair belongs in
`type.py`, not inline in `comparator.py`.

## Risks / Trade-offs

- **The fast path and `__call__` could disagree for a comparator segment,
  since they now reach the user's comparator by different routes — through
  `cmp_to_key` in one and directly in the other.** → This is the same drift
  risk `add-comparator-comparing` and `add-comparator-chaining` each carried,
  over new surface. Pinned by the spec requirement that the two agree, tested
  across every shape: bare comparator segment, two-argument form, reversed
  before and after chaining, mixed directions, null-tolerant, and on ties.
- **Arity dispatch changes the meaning of a two-argument callable passed to
  `then_comparing()`.** → Today that call raises `TypeError` on argument count
  at the first element; there is no working program whose meaning changes. The
  one shape that moves from broken to working — `nulls_first(cmp)` — moves in
  the safe direction and is spec'd rather than left as an accident.
- **`inspect.signature` is called at construction, and it is not cheap.** →
  Once per `then_comparing()` call, never per element or per comparison, which
  is the same budget `is_async_callable` already spends there under
  `callable-dispatch`.
- **A rejected async comparator is a divergence from Java, which has no async
  comparators to reject.** → Java's surface is matched in shape; the constraint
  exists only on the axis Java does not have. The error names both supported
  routes, and the restriction can be lifted later without a break.
- **Three README rows change state at once, two of them from struck-through.**
  → That is the point of doing them together; separately, two of them would
  keep citing a reason that has moved. No Migration entry is owed — nothing
  breaks.

## Migration Plan

Additive throughout. Every existing call site keeps its meaning, so there is
nothing to stage and nothing to deprecate. Rollback is removal of the new
parameter and the widened branch.

README's `java.util.Comparator` table needs three rows re-stated — the
`then_comparing(comparator)` row from "not yet implemented", and the
`comparing(f, keyComparator)` and `thenComparing(f, keyComparator)` rows from
struck-through — plus the signatures on the existing `comparing` and
`then_comparing` rows. `roadmap.md`'s **Later** row for this item is removed on
archive.
