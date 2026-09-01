## Why

`sorted()` over a stream containing `None` raises `TypeError` out of Python's own
comparison, and there is currently no way to say where the `None`s go short of
filtering them out and re-inserting them afterwards. Both shapes fail
identically today:

```
Stream([3, None, 1]).sorted()                     -> TypeError: '<' not supported between 'NoneType' and 'int'
Stream(records).sorted(comparing(lambda r: r["score"]))  -> same TypeError, when one score is None
```

Unlike the other Java 8 comparator gaps `enumerate-java-8-parity-gaps` filed,
this one is not parity for parity's sake — it is a user-facing hole with a
`TypeError` behind it. Java closes it with `Comparator.nullsFirst`/`nullsLast`.

The two failures above look like one bug to a caller and are two mechanisms
underneath: a null **element**, which never reaches a key extractor at all, and
a null **key**, extracted successfully and then compared. Java only names the
first; it reaches the second through `comparing(f, nullsFirst(naturalOrder()))`,
an overload README declines. This change closes both, because closing only the
element case would leave the more common Python shape — a record whose field is
sometimes `None` — still raising, with the Java route to it still shut.

Closing the key case does **not** depend on roadmap gap 4
(`then_comparing(Comparator)`, moved to **Later** on 2026-09-01). A null-tolerant
column is a key transform on a key extractor; it needs no comparator segment, so
the sync/async asymmetry that blocks gap 4 is not on this path. See design.md.

## What Changes

- **New:** `nulls_first(comparator=None)` and `nulls_last(comparator=None)` in
  `comparator.py`, matching Java's `Comparator.nullsFirst`/`nullsLast`. A `None`
  element orders before (respectively after) every non-`None` element; two
  `None`s compare equal; two non-`None` elements are ordered by the wrapped
  comparator, or are all equivalent when none is supplied, as in Java.
- **Null-tolerance is carried on the segment, not bolted on outside it.** Given a
  `KeyComparator`, `nulls_first`/`nulls_last` return a `KeyComparator` whose
  segments are null-tolerant, so `sorted()` keeps the decorate-sort-undecorate
  fast path instead of dropping to `cmp_to_key`. Given any other `Comparator`, or
  none, they return a plain wrapping comparator — the same polymorphism on the
  argument that `then_comparing()` already has.
- `sort()`'s column extraction gains a null-tolerant lane: a tolerant segment's
  column holds `(0, None)` for a null and `(1, key)` otherwise. Tuple comparison
  settles a null-vs-null pair on the leading component and never evaluates
  `None < None`, so the sort stays in C.
- `reversed()` on a null-tolerant chain flips where the nulls go, matching Java's
  `nullsFirst(c).reversed()`. This falls out of negating the leading component
  rather than being a separate rule.
- `KeyComparator.__call__` — the path `min()`, `max()`, `min_by()` and `max_by()`
  take — honours null tolerance too, so the fast path and the `__call__` path
  agree on the same ordering, as `comparator-comparing` already requires.
- **Not breaking.** Every ordering that sorts today sorts identically: null
  tolerance is opt-in per comparator, and a stream with no `None` in it never
  builds a tolerant column. A stream *with* a `None` in it raises `TypeError`
  today, so there is no prior behaviour to preserve.

## Capabilities

### New Capabilities

- `comparator-null-ordering`: where `None` sorts relative to non-`None` values,
  for both null elements and null extracted keys; how a null-tolerant comparator
  composes with `then_comparing()` and `reversed()`; and that the sorting fast
  path and the `__call__` path agree on the result.

### Modified Capabilities

None. `comparator-contract`, `comparator-comparing` and `comparator-chaining`
keep every requirement they state: this change adds a way to build a comparator,
and does not alter what any existing one does.

## Impact

- `src/snakestream/comparator.py` — the two new factories, and whatever the
  segment representation needs to carry tolerance.
- `src/snakestream/sort.py` — the null-tolerant column lane in `_column()` /
  `_sort_by_key()`.
- `src/snakestream/type.py` — any new alias the segment representation needs
  (per the project's rule that composite types live there, not inline).
- `README.md` — the `Comparator` parity table's `nulls_first`/`nulls_last` row
  moves from "not yet implemented" to implemented, plus a Migration-log entry.
- `roadmap.md` — **Now** -> **Queued changes** gap 5 retires.
- New tests; no existing test's expectations change.
