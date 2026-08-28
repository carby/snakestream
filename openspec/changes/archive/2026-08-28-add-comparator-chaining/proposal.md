## Why

`comparing()` landed on 2026-08-27 and proved the unwrapping mechanism: `sort()`
recognizes the value it returns and extracts each element's key exactly once
instead of once per comparison. That change deliberately deferred
`thenComparing()` — "genuinely useful, and cheap once the unwrapping mechanism
exists (a tuple key stays one C sort), but its composition rules should be
designed after the single-key case has proven the mechanism." The mechanism is
proven, so only the design pass was outstanding; roadmap open question 1 is that
pass.

Two things make chaining worth more than the tuple-key workaround the README
currently recommends. First, an async key extractor cannot appear inside a tuple
literal at all — `comparing(lambda x: (a(x), b(x)))` cannot await, and an
`async def` rewrite serializes the extractions that a chain runs concurrently.
Second, a multi-key sort usually wants mixed directions ("department ascending,
salary descending"), which no single tuple key expresses.

## What Changes

- `_KeyComparator` becomes public `KeyComparator` and holds an ordered tuple of
  **directed segments** — `(key_extractor, descending)` pairs — rather than one
  extractor. `comparing(f)` returns a single ascending segment, so every
  existing use is unchanged.
- **New:** `KeyComparator.then_comparing(other)` returns a **new**
  `KeyComparator` with `other` appended: either a key extractor (one ascending
  segment) or another `KeyComparator` (its segments spliced in, directions
  intact). Matches Java's `Comparator.thenComparing`.
- **New:** `KeyComparator.reversed()` returns a **new** `KeyComparator` with
  every current segment's direction flipped. This is Java's
  `Comparator.reversed()` exactly: flipping each component of a lexicographic
  order is the same as negating the composite, so
  `comparing(a).thenComparing(b).reversed()` and
  `comparing(a).reversed().thenComparing(b)` differ as they do in Java.
- `sort()`'s fast path generalizes from one key to a tuple of keys: extract each
  segment's column, zip the columns into per-element tuples, one Timsort over
  the tuples. Tuple comparison *is* lexicographic tie-breaking, so chaining
  costs no extra sort pass and short-circuits on the first differing component
  in C.
- Columns are extracted concurrently with each other, so a chain of k async
  extractors over n elements has k×n extractions in flight rather than k
  sequential rounds of n. This is the capability's main reason to exist.
- `KeyComparator.__call__` — the path `min()`, `max()`, `min_by()` and
  `max_by()` use — walks the segments, negating the sign on a descending one and
  short-circuiting on the first non-zero result.
- `comparing()`'s return annotation changes from the `Comparator` alias to
  `KeyComparator`, so the chaining methods are visible to `ty`. `KeyComparator`
  remains assignable to `Comparator` everywhere one is accepted.
- Not breaking. No existing signature changes, no existing behaviour changes,
  and the renamed class was private with no callers outside `comparator.py` and
  `sort.py`.

Explicitly **out of scope**:

- **A 3-way `Comparator` as a chain segment** (Java's
  `thenComparing(Comparator)` overload). Java separates it from
  `thenComparing(Function)` by static overload resolution — a wart there,
  needing explicit lambda parameter types to disambiguate — and Python has no
  equivalent: sniffing arity is unreliable for partials, builtins and `*args`
  callables. Refusing it also keeps the tuple invariant total, so the fast path
  can never be lost and there is no "sync comparator segments tuple via
  `cmp_to_key`, async ones cannot" asymmetry. The workaround is that a chain
  must begin at `comparing()`.
- **The `keyComparator` overloads** — `comparing(f, keyComparator)` and
  `thenComparing(f, keyComparator)` — for the same reason.
- **A `reverse=` keyword on `then_comparing()`.** `comparing(dept)
  .then_comparing(comparing(salary).reversed())` already expresses it, and a
  second spelling would collide confusingly with `sorted(reverse=True)`, which
  means something subtly different (buffer reversal, which flips tied elements;
  `reversed()` is comparator negation, which does not).
- **Changing what `sorted(reverse=True)` does.** It reverses the buffer after
  sorting, flipping tied elements too. That stays as it is; this change only
  pins it with a test now that it can stack with comparator negation.

## Capabilities

### New Capabilities
- `comparator-chaining`: `then_comparing()` and `reversed()` on the value
  `comparing()` returns — that chained ordering is lexicographic over the
  segments, that `reversed()` negates the composite, that both return new
  comparators rather than mutating, that every segment's extractor may be sync
  or async, and that sorting extracts each segment's key exactly once per
  element.

### Modified Capabilities
- `comparator-comparing`: the "applies the key extractor once per element"
  requirement is restated for a chain (each segment's extractor exactly once per
  element, eagerly — even when an earlier segment already decides every
  comparison), and the divergence from the lazy, short-circuiting direct-call
  path is made explicit, including that eager extraction surfaces an extractor
  error the lazy path would never reach.

## Impact

- `src/snakestream/comparator.py` — `_KeyComparator` renamed and given
  directed segments, `then_comparing()`, `reversed()`; `comparing()`'s return
  annotation.
- `src/snakestream/sort.py` — `_sort_by_key` splits into a per-column extractor
  and a tuple-aware sort with three lanes (all-ascending, all-descending,
  mixed); the `_KeyComparator` import follows the rename.
- `src/snakestream/type.py` — no new alias needed; `KeyComparator` is a concrete
  class, not a callable alias.
- `tests/test_comparing.py` (or a sibling) — chaining, direction, splicing, and
  concurrency coverage.
- `README.md` — the `java.util.Comparator` parity table: `thenComparing` and
  `reversed` move to implemented; the `keyComparator` overloads are recorded as
  deliberately skipped; the `comparing()` row's tuple-key note is updated to say
  when a tuple key is still the better answer; migration log entry.
- `roadmap.md` — open question 1 resolved.
