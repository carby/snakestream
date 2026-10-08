+++
id = "comparator-type-alias"
title = "Fixed the `Comparator` type alias mismatch"
filed = 2026-08-11
closed = 2026-08-11
outcome = "shipped"
+++

Fixed the `Comparator` type alias mismatch (`type.py:16`): kept a single
Java-style 3-way *int* `Comparator` (matching `sorted()`'s existing usage
and Java's own `Stream.min/max(Comparator)`), rather than splitting into
two aliases, and fixed `Stream.min()`/`max()`/`_min_max()` (`stream.py`)
to interpret the comparator's sign directly instead of treating it as a
bool. This also fixed the tie-break bug for free: both `min()` and `max()`
now keep the first of equal elements. Tracked as **BREAKING** in README's
migration log per `CLAUDE.md` since bool-returning comparators passed to
`min()`/`max()` now behave differently.
