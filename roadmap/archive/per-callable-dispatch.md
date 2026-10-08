+++
id = "per-callable-dispatch"
title = "Specialized `callable_dispatch.py`'s dispatch from per-result to per-callable"
filed = 2026-08-18
closed = 2026-08-18
outcome = "shipped"
+++

Specialized `callable_dispatch.py`'s dispatch from per-result to
per-callable: `is_async_callable(fn)` classifies a callable once
(recognizing a plain `async def` function and a callable object whose
`__call__` is `async def`), and the 26 per-element call sites across
`stream.py`, `collector.py` and `sort.py` hoist an `is_async` flag out of
their loop instead of calling `inspect.isawaitable` on every result.
A first-invocation `isawaitable` check is kept as a safety net so a
sync-signatured callable that returns a coroutine (the defect
`add-maybe-await-helper` fixed) is still handled correctly. `_maybe_await`
is retained for the handful of call sites invoked once per composition
(e.g. `collect()`'s `supplier`), where specialization buys nothing.
Measured in this repo's dev environment (Python 3.14.5, 20,000 elements,
a chain of 8 `.map()` ops, best of 5 runs): 5,949 ns/element before,
2,247 ns/element after — a 2.6x speedup, in line with the throwaway
benchmark harness's 5,775 → 2,064 ns/element (2.8x) recorded in
`design.md`. Carries one deliberate contract narrowing, tracked as
**BREAKING** in README's migration log: a callable invoked once per
element must be consistently sync or consistently async — one that
returns an awaitable for some elements and a plain value for others is no
longer supported (it has no Java analogue). See
`openspec/changes/optimize-callable-dispatch`.
