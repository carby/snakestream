## Context

`stream.py` accepts sync or async user-supplied callables everywhere (predicates, mappers, comparators, consumers, accumulators), per `type.py`'s `Awaitable`-union aliases. The current dispatch pattern, repeated at 10 sites, is:

```python
if iscoroutinefunction(fn):
    result = await fn(*args)
else:
    result = fn(*args)
```

This is wrong for callable *objects* (instances of a class defining `async def __call__`): `iscoroutinefunction(instance)` is `False` even though calling `instance(...)` returns a coroutine, so the sync branch runs, no `await` happens, and the coroutine object flows downstream as if it were a real value — Python only raises a `RuntimeWarning`, never an exception. `all_match`/`any_match`/`none_match` additionally duplicate ~12 lines of near-identical short-circuit-loop structure around this pattern.

## Goals / Non-Goals

**Goals:**
- One helper, `_maybe_await`, that correctly dispatches both plain sync/async functions and sync/async callable objects.
- Replace all `map`/`filter`/`peek`/`sorted`/`reduce`/`min`/`max`/`for_each`/match-family dispatch sites with it. (`find_any()` was originally assumed to be one of the 10 but doesn't take a callable at all — it has no dispatch site.)
- Collapse `all_match`/`any_match`/`none_match` into one shared implementation.
- Add regression coverage for async-`__call__` callable objects across the affected ops.

**Non-Goals:**
- `flat_map`'s use of `iscoroutinefunction()` to *reject* coroutine-returning mappers up front is a different check (pre-call classification, not post-call awaiting) and is explicitly out of scope — it stays as-is.
- No change to `type.py`'s public type aliases or any public method signature.
- No change to `ParallelStream`'s task/racing logic beyond it transitively using the same helper via inherited `Stream` methods.

## Decisions

**Result-based dispatch, not type-based.** `_maybe_await(fn, *args)` calls `result = fn(*args)` unconditionally, then returns `await result if inspect.isawaitable(result) else result`. This replaces the pre-call `iscoroutinefunction(fn)` check with a post-call `isawaitable(result)` check.
- *Alternative considered*: broaden the pre-call check to `iscoroutinefunction(fn) or (callable(fn) and iscoroutinefunction(fn.__call__))`. Rejected — it's more code, still fragile against other awaitable-producing patterns (e.g. a sync function that conditionally returns a coroutine, or a `functools.partial`-wrapped async callable), and `isawaitable()` on the actual result is strictly more general and simpler.

**Placement: new `callable_dispatch.py` module**, not inline in `stream.py`. Superseded during implementation: `sort.py`'s `_merge` also needed `_maybe_await` (see below), and `sort.py` importing from `stream.py` would be circular (`stream.py` already imports from `sort.py`), so the helper needed its own module regardless of size. Named for what it contains rather than as a generic `util.py`/`helpers.py` catch-all.
- *Alternative considered*: `stream.py` module-level helper (original plan, before the `sort.py` dependency emerged). Superseded — see above.
- *Alternative considered*: put it in `type.py` alongside the aliases it serves. Rejected — `type.py` currently holds only type definitions, no runtime logic; mixing in a helper function changes that module's character for one call site's convenience.

**`sorted()`'s comparator dispatch required a different fix than the other 9 sites.** Discovered during implementation: `sorted()`'s `iscoroutinefunction(comparator)` check doesn't gate a single call-then-await — it picks between two different sort algorithms (`merge_sort`, whose `_merge` in `sort.py` unconditionally `await`s the comparator, vs. `list.sort()` with a sync `cmp_to_key(checked_comparator)` wrapper). `_maybe_await` can't be dropped into that shape as a like-for-like replacement. Resolved (user-confirmed) by moving `_merge` onto `_maybe_await` internally and always routing `sorted()` through `merge_sort` when a comparator is given, dropping the `cmp_to_key`/`list.sort()` branch entirely. This fully closes the async-callable-object gap for `sorted()`/`min()`/`max()` at the cost of always using merge sort (not Timsort) for any comparator-based sort, sync or async.
- *Alternative considered*: leave `sorted()`'s algorithm-selection `iscoroutinefunction()` check as-is, untouched by this change, and scope-cut it out of the proposal. Rejected by user in favor of full parity across all comparator-accepting operations.

**`all_match`/`any_match`/`none_match` collapse via a shared private loop parameterized by short-circuit predicate**, e.g. `async def _match(iterable, predicate, short_circuit_on: bool, default: bool)`, with the three public methods becoming thin wrappers:
- `all_match`: short-circuits (returns `False`) on first `False`, default `True` for empty stream.
- `any_match`: short-circuits (returns `True`) on first `True`, default `False` for empty stream.
- `none_match`: short-circuits (returns `False`) on first `True`, default `True` for empty stream.
- *Alternative considered*: keep three separate methods but only extract `_maybe_await`. Rejected — the proposal explicitly calls out the three methods as "near-identical," and the loop structure (not just the dispatch line) is duplicated; collapsing both concerns in one pass avoids touching this code twice.

## Risks / Trade-offs

- [Behavior change for pathological callables] A sync function that returns an awaitable *value* (not because it's async, but because e.g. it returns a `Future` or another coroutine as its actual result) would now have that awaitable awaited, whereas previously it would have been passed through as-is. → Mitigation: this matches Java/Python idiom (nothing in this codebase's contracts returns raw awaitables as data), and `type.py`'s aliases already document return types as plain values or `Awaitable[value]`, never `Awaitable`-as-data; no realistic caller is affected.
- [Regression risk from touching 10 call sites at once] → Mitigation: full existing test suite (`uv run pytest`, coverage-gated at 98%) must pass unchanged before adding new async-callable-object regression tests; sites are changed mechanically (same call, same args, swap dispatch mechanism) rather than restructured.

## Migration Plan

Single internal PR: add `_maybe_await`, replace call sites, collapse match family, add tests, run full suite + coverage gate. No feature flag or staged rollout needed — purely internal, no public API change, `main` is the only consumer branch. Rollback is a plain revert if the coverage gate or test suite catches a regression.

## Open Questions

None — scope and approach are fully determined by the proposal and `roadmap.md`'s existing analysis.
