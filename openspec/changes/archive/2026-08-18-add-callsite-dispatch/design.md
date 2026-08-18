## Context

`optimize-callable-dispatch` (shipped, see roadmap **Done**) replaced per-result
`isawaitable()` checks with per-callable classification and measured a 2.6x
speedup — 5,949 → 2,247 ns/element on a chain of 8 `.map()` ops over 20,000
elements. It bought that win by hoisting an `is_async` flag out of each
per-element loop, which meant touching 24 call sites and leaving the same five
branches at each one.

The result is `callable_dispatch.py` in its current shape: two small helpers
(`_maybe_await`, `is_async_callable`), a `_classify_step` escape hatch, and a
40-line comment block headed "Canonical shape for the 26 per-element call sites"
that spells the pattern out in code-in-a-comment form for future authors to copy.

The current state, precisely:

- **9 sites in `stream.py`** — `_FilterSink.accept`, `_MapSink.accept`,
  `_PeekSink.accept`, `_collect_mutable`, `reduce`, `for_each`,
  `for_each_ordered`, `_min_max`, `_match`. The three sinks hold their state on
  `self` (`self._is_async`, `self._checked`) since a sink instance *is* the
  per-composition object; the six terminals hold it in function locals. Each of
  the nine also carries a `cast("Awaitable[...]", r)` purely to tell `ty` that
  the `await` is legitimate.
- **14 sites in `collector.py`** — the six `summing_*`/`averaging_*` mappers,
  `_extremum`'s comparator, `reducing`'s mapper and binary operator, `to_map`'s
  key/value/merge functions, `grouping_by`'s classifier, `partitioning_by`'s
  predicate. Nine of these inline the shape; five route through `_classify_step`.
- **1 site in `sort.py`** — `merge_sort` classifies the comparator once and
  threads the state to every `_merge` call through the recursion as a
  positionally-indexed two-element list, `state = [is_async, checked]`.

Two constraints shape the design. First, the per-composition lifetime rule: the
existing comment warns that the flags must be hoisted "inside the per-composition
generator body (never in the enclosing function, or classification leaks across
compositions/branches)", which the `callable-dispatch` spec states normatively as
"Classification does not leak across compositions" and "Each parallel branch
classifies independently". Second, performance: this sits in the hottest loop in
the library and must not give back the 2.6x.

## Goals / Non-Goals

**Goals:**

- One object, constructed the same way everywhere, replaces the hand-copied
  five-branch shape at all 24 per-element sites.
- The per-composition lifetime rule becomes structural — you construct the object
  where you would have declared the flag pair — rather than a prose warning.
- `_classify_step` is deleted, and `to_map`/`reducing` stay under the mccabe gate
  without it.
- `sort.py`'s positional `state` list disappears.
- No measurable throughput regression on the established benchmark.
- No public API change and no behavior change; the existing test suite is the
  regression net and should pass unmodified.

**Non-Goals:**

- Changing which callables are classified as async, or the homogeneity contract
  `optimize-callable-dispatch` narrowed. `is_async_callable` is kept verbatim.
- Removing `_maybe_await`. It stays for once-per-composition sites
  (`collect()`'s `supplier`), exactly as the previous change decided.
- Touching the terminal ops' own structure. Rewriting the terminals as
  `TerminalSink`s is a separate roadmap item; this change only replaces the
  dispatch lines inside them, so the two changes do not collide.
- Converting `flat_map`'s `iscoroutinefunction` check. That is pre-call
  *rejection* of an `async def` flat mapper, not post-call awaiting — a
  distinction the current code already documents at `stream.py:321-323` and that
  this change preserves.

## Decisions

### Decision 1: A stateful callable object, not a decorator or a closure factory

`CallSite` wraps the callable plus its two classification flags and exposes
`async def __call__(self, *args)`:

```python
class CallSite:
    """One user-supplied callable, classified sync-or-async once and remembered.

    Construct one per callable per composition — never per operation, or the
    classification leaks across compositions and parallel branches.
    """

    __slots__ = ("_fn", "_is_async", "_checked")

    def __init__(self, fn: Callable) -> None:
        self._fn = fn
        self._is_async = is_async_callable(fn)
        self._checked = False

    async def __call__(self, *args: Any) -> Any:
        result = self._fn(*args)
        if self._is_async:
            return await result
        if not self._checked:
            self._checked = True
            if isawaitable(result):
                self._is_async = True
                return await result
        return result
```

Alternatives considered:

- **A closure factory** (`dispatch = make_dispatcher(fn)` returning an `async def`
  closing over `nonlocal` flags). Equivalent semantics and marginally faster
  (`nonlocal` beats an attribute load), but it produces an opaque function object
  that can't be introspected in a debugger or asserted on in a test, and the
  `nonlocal` rebinding is exactly the pattern the current comment struggles to
  explain. Rejected on legibility.
- **A decorator applied at the op boundary** (`@dispatched` on `filter`, `map`, …).
  Wrong lifetime: the decorator runs once when the op is *called*, but the flags
  must live once per *composition*, and an op is built once and composed many
  times. This is the precise failure the existing comment warns about, so a design
  that structurally invites it is disqualified.
- **Keeping `_classify_step` and just adding a wrapper.** Leaves two shapes in the
  codebase, which is the current problem plus one more thing.

### Decision 2: The call is `await site(x)`, so the site owns the await

`_classify_step` returns `(result, is_async, checked)` and leaves the caller to
decide whether to `await` — which is why `to_map` reads as three unpack-then-await
pairs. `CallSite.__call__` is itself `async` and always returns the settled value,
so every call site is `value = await site(element)` with no branch left over.

The cost is one coroutine frame per element even for a fully synchronous callable,
where the current inline code has none. That is the one real performance question
in this change and is treated as such in Risks below.

### Decision 3: Sinks hold `CallSite`s on `self`; terminals hold them in locals

This is not a new rule, just the existing one restated in terms of the new object.
A sink instance is built fresh per composition (`Op.link()` is called from
`_sequential` on every drive), so `self._predicate = CallSite(predicate)` in
`__init__` has exactly the right lifetime and is a direct swap for today's
`self._is_async`/`self._checked` pair. A collector closure body and a terminal
method body likewise run once per composition, so a local `site = CallSite(fn)`
above the loop is the direct swap for today's local flag pair.

The rule that must not be broken: never construct a `CallSite` in an `*Op`
`__init__`, in a collector *factory* (the outer `def summing_int(mapper)`), or
anywhere else that runs once per operation rather than once per composition. The
class docstring says so, and the spec's existing "does not leak across
compositions" scenarios are what catch it if violated.

### Decision 4: One `CallSite` per callable, never shared

`to_map` builds three (`key_mapper`, `value_mapper`, `merge_function`);
`reducing` builds two. This falls out naturally from the object model — you wrap
a callable, so two callables are two objects — but it is the one thing a
plausible "optimization" would get wrong, so it is stated normatively in the
delta spec and covered by a mixed sync/async test rather than left implicit.

`merge_function` is optional in `to_map`, so its `CallSite` is built only when
the argument is not `None`, mirroring today's
`is_async_callable(merge_function) if merge_function is not None else False`.

### Decision 5: `sort.py` threads a `CallSite`, replacing the `comparator, state` pair

`merge_sort(arr, comparator)` builds one `CallSite` and passes it down;
`_merge_sort` and `_merge` take `(arr, cmp)` and `(left, right, cmp)` instead of
carrying a separate `state` list alongside the raw comparator. The sharing
semantics are unchanged — one classification per `merge_sort` run, visible to
every sibling `_merge` — which is precisely what a single shared object gives.
`check_comparator_result_type(sign)` stays where it is, applied to the settled
value after the await.

### Decision 6: The 40-line canonical-shape comment is deleted, not updated

Its entire job was to let authors reproduce a pattern by hand. Once the pattern
is a class, the class is the documentation; what survives is a short docstring
carrying the only rule a caller still has to know (per-composition construction).
Keeping a prose restatement of code that now exists would be the same defect at
half the size.

## Risks / Trade-offs

- **One coroutine frame per element for sync callables, where the inline code had
  none.** This is the only plausible regression, and it is real: `await site(x)`
  allocates and drives a coroutine that today's `r = fn(x); if is_async: ...`
  does not. → Mitigation: benchmark before and after on the harness the previous
  change used (Python 3.14, 20,000 elements, chain of 8 `.map()` ops, best of 5)
  and record both figures in the roadmap entry the way
  `optimize-callable-dispatch` and `redesign-pipeline-sink-chain` both did.
  `__slots__` on `CallSite` keeps attribute access off a per-instance `__dict__`.
  If the measured cost is material, the fallback is a two-shape `CallSite` whose
  `__init__` picks a sync fast path — but that reintroduces branching complexity,
  so it is a fallback, not a plan. Do not proceed to the remaining call sites
  until the benchmark on a first converted site is understood.
- **The per-composition lifetime rule is now easier to violate silently**,
  because `CallSite(fn)` in a wrong scope looks just as reasonable as in the right
  one, whereas a bare `is_async = ...` at least sat visibly adjacent to its loop.
  → Mitigation: the `callable-dispatch` spec already has
  "Classification does not leak across compositions" and "Each parallel branch
  classifies independently" scenarios with tests behind them; those are the
  guard. Re-run them specifically after conversion rather than trusting the
  suite total.
- **A shared `CallSite` across two callables would silently corrupt a mixed
  sync/async `to_map` or `reducing`.** → Mitigation: the ADDED spec requirement
  plus a direct mixed-mode test for both operations.
- **Coverage gate.** `CallSite.__call__` has three exit paths (async, sync-first-
  call-not-awaitable, sync-thereafter) plus the sync-signatured-returns-coroutine
  path. All four are already exercised somewhere in the suite, but they are now
  concentrated in one function under a 98% branch gate instead of spread across 24
  sites. → Mitigation: `tests/test_callable_dispatch.py` gets direct `CallSite`
  unit tests for all four, independent of any stream operation.
- **Churn against an in-flight roadmap.** Five more cleanup items follow this one
  in **Now**, two of which (the `Op` ABC, terminals-as-sinks) touch the same
  files. → Mitigation: this change only replaces dispatch *lines*, never op or
  sink *structure*, so it rebases cleanly under the later items; it is sequenced
  first in the roadmap precisely so those items inherit the smaller shape.
