## Why

`_maybe_await` (`callable_dispatch.py`) is the single dispatch point for every
user-supplied callable in the library — 30 call sites across `stream.py` (13),
`collector.py` (15) and `sort.py` (2). It calls the callable and then decides
whether to await by inspecting the *result*, once per element per operation:

```python
async def _maybe_await(fn, *args):
    result = fn(*args)
    return await result if isawaitable(result) else result
```

Benchmarking (see `design.md` for the full data, method and raw numbers) shows
this dominates per-element cost. For a chain of 8 `.map()` ops over 20,000
elements on Python 3.14, the pipeline spends **5,775 ns per element**; the same
chain with dispatch specialized per callable instead of per result spends
**2,064 ns** — a **2.8x** speedup — against a theoretical floor of 2,030 ns for
a version with no async support at all. The overhead is `inspect.isawaitable`
itself, not the `async def` wrapper: merely inlining `_maybe_await` into the
call sites recovers only ~20%, because `isawaitable` performs three checks
including a `collections.abc.Awaitable` ABC `isinstance` on every result.

This is worth doing on its own terms. It was surfaced while sizing the
roadmap's **Next**-bucket Sink-chain redesign, whose measured speedup is 15–17%
at a far larger blast radius — this change is both cheaper and 
substantially faster, and the two are independent.

## What Changes

- Replace result-based dispatch with **callable-based dispatch decided once per
  composition**. Each call site hoists an `is_async` decision out of its
  per-element loop, keeping a single loop body:

  ```python
  is_async = is_async_callable(mapper)  # hoisted, once
  checked = False
  async for i in iterable:
      r = mapper(i)
      if is_async:
          r = await r
      elif not checked:  # first-element safety net
          checked = True
          if isawaitable(r):
              is_async = True
              r = await r
      yield r
  ```

- Add `is_async_callable(fn)` to `callable_dispatch.py`, classifying both plain
  `async def` functions and callable objects with an `async def __call__`:

  ```python
  def is_async_callable(fn):
      if iscoroutinefunction(fn):
          return True
      call = getattr(type(fn), "__call__", None)
      return call is not None and iscoroutinefunction(call)
  ```

- Keep the first-invocation `isawaitable` safety net. Build-time classification
  alone is **not** sufficient: a callable with a sync `__call__` that returns a
  coroutine is classified sync and would leak an un-awaited coroutine — the
  exact class of bug `_maybe_await` was introduced to fix (see roadmap Done,
  `add-maybe-await-helper`). The measured cost of the safety net is nil
  (2,064 ns vs. 2,018 ns for an unsafe two-loop variant).

- **Narrow the dispatch contract** from per-result to per-callable: a callable's
  awaitability is decided at its first invocation in a composition and held for
  the remainder of that composition. A callable that returns an awaitable for
  some elements and a plain value for others is no longer supported. This is a
  deliberate, specified narrowing (see `specs/callable-dispatch/spec.md`).

- Retain `_maybe_await` for call sites invoked once per composition rather than
  once per element (e.g. `collect()`'s supplier), where specialization buys
  nothing and the helper is clearer.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `callable-dispatch`: dispatch is decided per callable per composition rather
  than per result; adds the first-invocation classification contract and the
  homogeneity requirement that follows from it. All four existing scenarios
  (sync function, async function, sync callable object, async callable object)
  are preserved unchanged.

## Impact

- `src/snakestream/callable_dispatch.py`: add `is_async_callable`; `_maybe_await`
  retained for per-composition call sites.
- `src/snakestream/stream.py`: 13 call sites.
- `src/snakestream/collector.py`: 15 call sites.
- `src/snakestream/sort.py`: 2 call sites (`_merge`).
- `tests/test_callable_dispatch.py`: extend for the new classification contract.
- No public API change; no signature change. Behavior narrows only for
  heterogeneous callables (specified above), tracked as **BREAKING** in
  README's migration log per `CLAUDE.md`'s convention.
- Classification state is per-composition (a local inside the op's generator),
  not per-op, preserving the existing rule that op state must not leak across
  separate compositions of the same chain (see `fix-stream-rerun-state`).
