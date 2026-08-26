## Context

See proposal.md — Why for the motivation and the measurements.

Three facts about the existing code shape this design:

1. **`Comparator` is a type alias, not a class.** `type.py` defines it as
   `Callable[[T, T], int | Awaitable[int]]`. There is no interface to hang a
   static factory off, the way Java hangs `comparing` off `Comparator`. So
   `comparing()` is a module-level function, and whatever it returns must
   satisfy a structural `Callable` type rather than a nominal one.

2. **`sort()` already dispatches on a property of the comparator.** It asks
   `is_async_callable(comparator)` and picks between `merge_sort` and
   `list.sort`. Adding a key fast path is one more question asked in the same
   place, not a new kind of indirection.

3. **`comparator.py` holds comparator *semantics*; `sort.py` holds sorting
   *algorithms*.** That split was made deliberately (see the migration log entry
   for the 2026-08-25 `comparator.py` split out of `sort.py`) precisely because
   `min`/`max`/`min_by`/`max_by` consume comparator semantics while sorting
   nothing. `comparing()` is comparator semantics, and its consumers include
   those same non-sorting operations, so it belongs in `comparator.py`. The
   import edge stays one-way: sorting calls semantics, never the reverse.

## Goals / Non-Goals

**Goals:**

- One key extraction per element when sorting, for both sync and async
  extractors.
- `comparing()` usable by every comparator-consuming operation with no
  signature changes.
- The fast path must be an optimisation, not a semantic fork: the same ordering
  must result whether or not a consumer knows about it.

**Non-Goals:**

- Optimising `min()`/`max()`/`min_by()`/`max_by()` for keys. They are O(n)
  comparisons already; a key path would halve their extractor calls (a
  comparison calls the extractor twice), but that is a smaller and separable
  win. They must *work* with `comparing()` — via the plain callable path — and
  need not be fast for it in this change.
- Any change to `merge_sort`, the trial probe, `_checked`, or the async
  comparator's existence. See proposal.md — out of scope.

## Decisions

### `comparing()` returns an object carrying the extractor, not a closure

A literal port of Java's `(a, b) -> k(a).compareTo(k(b))` is not merely
unhelpful here, it is a **regression**: the extractor would be called twice per
comparison, O(n log n) times, so an async extractor would cost `2n log n`
awaits against `merge_sort`'s `n log n`. The entire benefit depends on the sort
being able to see the extractor rather than an opaque two-argument function.

So `comparing()` returns a small object exposing the extractor as an attribute
and implementing `__call__` with the ordinary comparison semantics. `sort()`
tests for the attribute; anything that does not know to look still gets a
working `Comparator`.

*Alternatives considered:*

- **A `key=` parameter on `sorted()`.** Pythonic and mirrors the builtin, but it
  is not Java surface, it does not reach `min`/`max`/`min_by`/`max_by` without
  adding the same parameter to four more call sites, and it introduces an
  interaction to specify between `key=` and `comparator=`. Rejected: one
  factory upgrades every consumer at once and changes no signature.
- **A marker on a plain function** (setting an attribute on a closure). Works,
  but a function with a smuggled attribute is harder to type and to introspect
  than a small class, and gives `ty` nothing to check.
- **Sniffing arity or unwrapping `functools.partial`.** Fragile and implicit;
  rejected outright.

### The fast path is decorate–sort–undecorate, and needs no tie-break index

Extract the keys, pair them with their elements, sort on the key alone, unzip.
Because Timsort is stable, pairing on the key alone already preserves encounter
order for equal keys — no index column is needed, and crucially the *elements*
are never compared, so elements that do not support `<` sort fine as long as
their keys do. Sorting `(key, element)` tuples without an explicit key selector
would compare elements on ties and break both properties.

### The key path performs no sign or bool validation

`comparator-contract` makes `sorted()`/`min()`/`max()` responsible for raising
`TypeError` on a `bool` comparator result, because `bool <: int` lets a boolean
predicate satisfy the `Comparator` type while never being able to signal "orders
before". A key extractor returns a *key*, not a sign — there is no sign to
misinterpret, and `False < True` is a perfectly ordinary ordering. So the fast
path skips `check_comparator_result_type`, `_checked` and the trial probe
entirely. This is a deliberate absence, recorded in the spec as its own
requirement so it does not read as an oversight later.

Incomparable keys surface as the `TypeError` `list.sort` already raises. Nothing
catches or re-wraps it: matching the builtin is the clearest contract available.

### Async extraction is a gather-then-sort, classified once

Awaitability is classified once per composition, per the `callable-dispatch`
convention, not per element — `is_async_callable(extractor)` decided once, with
the standard one-time `isawaitable` safety net for a callable with a plain
`def __call__` returning a coroutine. Unlike `sort()`'s existing sync path,
there is no need for a pre-flight trial comparison here: key extraction happens
inside an `async` loop where an `await` is always available, which is exactly
the property `list.sort`'s C loop denies. The trial probe exists because Timsort
offers no such point; the key path never needs it.

Whether the extractions run sequentially or concurrently (`asyncio.gather`) is
left open — see Open Questions.

### Export as a top-level name

`__init__.py` currently exports only `Stream` and `PROCESSES`; `Collector` and
the collector factories are imported from their own modules, mirroring Java's
`Collector`/`Collectors` split. `comparing()` follows the same rule and is
imported from `snakestream.comparator`, not re-exported at the top level. This
keeps the module split visible in user code and matches how `collectors` is
already used.

## Risks / Trade-offs

- **The fast path and the `__call__` path could drift, giving different orders
  for the same comparator.** → The spec requires the direct-call sign contract
  and the sorted order independently; tests must assert both agree, including
  on ties and on `None`/`bool`/mixed-type keys.
- **Users may expect `comparing()` to compose (`thenComparing`) and find it does
  not.** → Out of scope by decision, not oversight; the docstring should say so
  and point at the tuple-key workaround (`comparing(lambda x: (a(x), b(x)))`),
  which already works and is exactly what a future `thenComparing()` would
  compile to.
- **`reverse=True` on `sorted()` interacts with a key ordering.** →
  `_SortedSink` reverses the buffer after sorting, which is order-reversal
  rather than comparator-negation, so equal-key runs are reversed too. That is
  the behaviour comparators already get today; the risk is only that it now
  applies to a second construction. Needs a test pinning the existing semantics
  rather than a change.
- **A new public name is permanent surface pre-1.0.** → It is a direct Java port
  with a Java name, which is the project's stated rule for naming, so the odds
  of wanting to rename it later are low.
- **Extractor called once per element is a spec'd guarantee, so a future
  implementation cannot silently re-derive keys.** → Accepted deliberately: it
  is the property the capability exists for, and users with expensive or
  side-effecting extractors will rely on it.

## Migration Plan

Purely additive. No existing behaviour changes, no deprecation, nothing to
migrate. `comparing()` is an alternative way to build a comparator; every
existing comparator keeps working on its existing path.

The README needs a new parity table: the current tables cover `Stream` and
`Collectors`, and `java.util.Comparator` is a third interface with no table yet.
That table should also record the deliberately-skipped members
(`thenComparing`, `reversed`, `naturalOrder`, `reverseOrder`) with their reasons,
in the same style the `Stream` table uses for struck-through entries — otherwise
the next reader cannot tell "not yet" from "decided against".

## Open Questions

- **Sequential extraction or `asyncio.gather`?** Gathering would overlap I/O for
  an async extractor and could dominate the win for genuinely I/O-bound keys,
  but it changes failure semantics (first error vs. all errors), memory profile,
  and the order side effects are observed in. Safely deferrable: it is an
  implementation detail behind a spec that only constrains the invocation
  *count*, so it can be settled with a benchmark during implementation without
  reopening the spec or the task breakdown.
- **Does the key path want to be reused by `min`/`max`?** Named as a non-goal
  above; worth revisiting once the mechanism exists, and it changes nothing here
  if the answer is later yes.
