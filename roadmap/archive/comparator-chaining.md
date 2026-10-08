+++
id = "comparator-chaining"
title = "`Comparator.thenComparing()`/`reversed()` chaining lands"
filed = 2026-08-28
closed = 2026-08-28
outcome = "shipped"
+++

**`Comparator.thenComparing()`/`reversed()` chaining lands** (2026-08-28),
resolving **Now** open question 1. The previously-private `_KeyComparator`
becomes public `KeyComparator` holding an ordered tuple of
`(key_extractor, descending)` segments instead of one extractor;
`comparing(f)` still produces exactly one ascending segment, so every
existing call reaches the code it reached before.
`KeyComparator.then_comparing(other)` appends a segment or splices in
another `KeyComparator`'s segments with their directions intact;
`.reversed()` flips every current segment's direction — flipping each
component of a lexicographic order equals negating the composite, which is
what reproduces Java's before/after-chaining distinction with one
implementation rather than two.

`sort()`'s fast path generalizes from one key to k: columns are extracted
concurrently across segments (not just within one, as before) via
`asyncio.gather`, zipped into per-element tuples, and sorted in one Timsort
pass across three lanes — all-ascending, all-descending via
`sort(reverse=True)` (CPython's sort is stable in the strong sense under
`reverse=True`, so this is exactly comparator negation, ties included, not
a post-hoc buffer reversal), and mixed via a `_Descending` wrapper applied
only to the columns that asked for one. Measured: a 2-segment chain over
20,000 `(int, int)` tuples costs ~12ms all-ascending against ~40ms mixed
(one descending segment) — the `_Descending.__lt__` indirection is the only
place this capability leaves C, and it is paid only in the mixed lane. The
single-ascending-segment case takes the exact pre-chaining code path — no
tuple build, no outer gather — so `add-comparator-comparing`'s measured
figures stand unchanged.

README's `java.util.Comparator` table moves `thenComparing`/`reversed` from
struck-through "decided against" to implemented, and records the
`keyComparator` overloads as a deliberate skip instead — Python cannot
disambiguate a one-argument key extractor from a two-argument comparator by
signature, and accepting one would break the "every segment yields a key"
invariant the fast path depends on being total. Not breaking: purely
additive apart from the rename of a name with two in-repo references and no
outside callers. See `openspec/changes/add-comparator-chaining`.
