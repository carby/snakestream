+++
id = "python-floor-sequence"
title = "The Python floor sequence: 3.10 -> 3.14"
filed = 2026-09-04
closed = 2026-09-04
outcome = "shipped"
shipped_as = "raise-python-floor-to-311 .. raise-python-floor-to-314"
+++

**The Python floor sequence: 3.10 -> 3.14** (2026-09-04) — four changes,
`raise-python-floor-to-311` through `-314`, one minor version each. Split
rather than batched on reviewability: each unlocks a *different* lint family
and the last two rewrite annotations across most of `src/`, so batched, the
one behavioural deletion would have been invisible among ~40 mechanical
rewrites.

| step | what it deleted |
|---|---|
| 3.11 | the `sys.version_info` fork in `close()`; a `PERF203` suppression ruff stops raising on 3.11+ |
| 3.12 | PEP 695 — `class Stream[T]`, `type` aliases; unquoted `FlatMapper` via the lazy RHS |
| 3.13 | PEP 696 — 14 `AsyncGenerator[T, None]` -> `AsyncGenerator[T]` |
| 3.14 | PEP 649 — 17 quoted annotations unquoted, 13 in `comparator.py` |

**The point was never the versions.** Free-threading (PEP 779) is officially
supported only on 3.14, and it is the substrate the two changes above stand
on. Recorded because the sequence reads as housekeeping and was not.

Two typing features were checked against the code and **declined**, so the
questions are not re-opened. **PEP 681 (`dataclass_transform`)** has no
possible site: it exists for a library shipping its own dataclass-like
decorator, and this package ships none. **PEP 646 (variadic generics)** has
one candidate — `sort.py`'s multi-key column tuple — and it earns nothing:
the key types are erased deliberately (`KeyExtractor` returns `Any`), the
tuple's element types change mid-flight (`_tolerant_column()` rewrites keys
into `(present, key)` pairs), and segment identity is decided at runtime by
signature inspection, which no checker can follow. **PEP 696 defaults on
`Collector[T, A, R]`** were declined too: `A` is `Any` at 28 of 45 annotation
sites and is the parameter that wants a default, but PEP 696 defaults must be
trailing, so only `R` can take one — and reaching `A` would mean reordering a
public generic, a silent type-level break.
