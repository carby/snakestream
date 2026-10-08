+++
id = "normalize-dead-next-branch"
title = "Fixed the dead `__next__` branch in `_normalize()`"
filed = 2026-08-20
closed = 2026-08-20
outcome = "shipped"
+++

**Fixed the dead `__next__` branch in `_normalize()`.** The guard admitted a
source on `hasattr(source, "__iter__") or hasattr(source, "__next__")` while
the body was `for i in source`, so a sync iterator implementing only
`__next__` passed the guard and then died with `TypeError: 'X' object is not
iterable`. **Decided to make the advertised support real rather than narrow
the guard**, because three things already promised it and only the code
disagreed: README lists `Iterator` among accepted sources, the
`stream-construction` spec's "Iterable source spreading" requirement names
`__next__` explicitly, and `_maybe_aclosing`'s docstring exists precisely so
a bare `__anext__`-only async iterator works — narrowing would have meant
retracting a capability in all three and leaving the sync and async sides
deliberately asymmetric.

`__iter__` is still checked first, so lists, tuples and every other plain
iterable run exactly the code they did before (`next([1, 2, 3])` is a
`TypeError`, so one merged path was never an option); the new arm only
catches sources with `__next__` and no `__iter__`. The non-obvious part is
PEP 479: a `StopIteration` escaping an async generator body surfaces as
`RuntimeError: async generator raised StopIteration`, so the loop guards the
`next()` call alone and keeps the `yield` outside the `try` — which also
means a `StopIteration` thrown in at the yield still propagates instead of
being swallowed into a silent end-of-stream.

Behaviour-preserving for every source that worked before; the only sources
whose behaviour changed are ones that raised `TypeError`. No public API
change, so no migration-log entry. Seven tests added in
`tests/test_normalize.py`, including an `assert not hasattr(obj, "__iter__")`
guard so they can't drift onto the `__iter__` path, the immediately-exhausted
case that covers the `except StopIteration` arm, and a laziness check that
`limit(2)` advances the source exactly twice. See
`openspec/changes/archive/2026-08-20-fix-next-only-source-normalization`.
