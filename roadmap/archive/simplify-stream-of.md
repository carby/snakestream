+++
id = "simplify-stream-of"
title = "Simplified `Stream.of()` to two cases"
filed = 2026-08-11
closed = 2026-08-11
outcome = "shipped"
+++

Simplified `Stream.of()` (`stream.py`) from a four-way branch on dict vs.
list vs. multiple positional args vs. kwargs down to two cases: a single
positional arg passes straight through to `Stream()`'s existing source
normalization, multiple args wrap into a list (one element each). The
dict/list `isinstance` special-casing turned out to be dead complexity —
tracing all 15 existing `test_of.py` cases showed it always produced the
same call as the generic path, since `_normalize()` already re-spreads
lists/dicts on its own. Also fixed `_normalize()` (`base_stream.py`) to
treat `str`/`bytes` as scalar values, matching how Java's `Stream.of(T...)`
treats `String`/`byte[]` atomically (byte arrays can't decompose via
varargs since `T` can't bind to a primitive type), instead of the previous
silent char-by-char/byte-by-byte spreading. Both changes are **BREAKING**
and tracked in README's migration log per `CLAUDE.md`: `**kwargs` support
is removed from `Stream.of()` entirely (no Java equivalent, undiscoverable,
no real use case over `Stream.of(*some_dict.items())`), and
`Stream.of("abc")`/`Stream.of(b"ab")` now yield one element instead of
spreading.
