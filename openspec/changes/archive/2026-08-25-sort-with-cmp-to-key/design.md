## Context

See proposal.md — Why for the motivation and the measured figures.

Three existing facts shape the approach:

1. **`merge_sort` already classifies.** `sort.py:33` builds
   `state = [is_async_callable(comparator), False]` and threads it through
   every `_merge` call, so the sync/async decision is made once per run today.
   The fast path does not need a new classification mechanism; it needs the
   existing one hoisted one level up, above the choice of algorithm.
2. **`comparator-contract` makes `sorted()` responsible for rejecting `bool`.**
   `check_comparator_result_type` is called on every settled sign inside
   `_merge`. Under `cmp_to_key` there is no library code between the comparator
   and the sort unless we put some there.
3. **`callable-dispatch` requires the one-time `isawaitable` safety net.** A
   plain-`def` `__call__` returning a coroutine classifies sync;
   `test_sorted_sync_call_returning_coroutine_comparator` and
   `test_sorted_async_callable_object_comparator` both pin the behaviour.
   `merge_sort` catches it on the first comparison (`state[1]`), inside an
   `async def`. `list.sort` is sync all the way down — a coroutine seen mid-sort
   cannot be awaited from inside the key function.

## Goals / Non-Goals

**Goals:**

- Sync comparators sort with Timsort; async comparators keep `merge_sort`.
- One place — `sort.py` — decides which, so `_SortedSink.end()` states intent
  rather than algorithm.
- Every existing `sorted()` test passes unmodified.

**Non-Goals:**

- Renaming `sort.py`. Story 5 does that, deliberately after this change, so
  this diff stays readable.
- Touching `is_new_extremum` / the `min`/`max` / `min_by` / `max_by` path.
  Those compare once per element with no sort algorithm to choose between.
- Recovering the 3.6x figure by dropping the `bool` check. See Decisions.
- Annotating the rest of `sort.py`. Only the new function is annotated; the
  module-wide pass belongs to story 5.

## Decisions

### The split lives in `sort.py`, behind one new `sort(arr, comparator)`

`_SortedSink.end()` should say *sort this buffer with this comparator*, not
*pick a sorting algorithm based on how the comparator was spelled*. Putting the
`if is_async` in `ops.py` would push comparator-dispatch knowledge into the op
module, which is exactly what `sort.py` exists to hold.

Shape:

```python
async def sort(arr: list[Any], comparator: Comparator) -> list[Any]:
    if is_async_callable(comparator):
        return await merge_sort(arr, comparator)
    if len(arr) > 1:
        trial = comparator(arr[0], arr[1])
        if isawaitable(trial):
            await trial
            return await merge_sort(arr, comparator)
        check_comparator_result_type(trial)
    arr.sort(key=cmp_to_key(_checked(comparator)))
    return arr
```

**Revised during implementation (user-approved).** This section originally
said `merge_sort` would keep its `state` list untouched. That turned out to be
impossible to hold: once `sort()` settles asyncness ahead of the call, every
comparator reaching `merge_sort` returns awaitables — either `is_async_callable`
said so, or the trial proved it — so `_merge`'s `elif not state[1]` ladder can
never fire. Branch coverage caught it immediately as two unreachable arms.

`merge_sort` therefore drops the `state` list entirely: it recurses into itself
rather than into a `_merge_sort` that exists only to thread state, and `_merge`
does a plain `sign = await comparator(left[i], right[j])`. That is ten lines
lighter and says what is true — *this function is the async path* — where the
surviving ladder would have said the opposite. It is the same removal this batch
made to `_ForEachSink._finish`: an ordering that looks load-bearing to a reader
but cannot fire.

The async path is measurably unaffected (6.7 ms -> 6.8 ms on a 2,000-element
async-comparator sort, best of 9 — within noise), so this is a legibility and
coverage change, not a second performance claim.

Returning `arr` even though `arr.sort()` is in place keeps one signature for
both branches; `merge_sort` returns a new list and cannot be made in-place
without rewriting it.

### The safety net is one trial comparison, taken before the sort

The open question the roadmap left for this proposal. Two candidates:

- **(chosen) One trial comparison ahead of the sort.** When classification says
  sync and the buffer holds at least two elements, call
  `comparator(arr[0], arr[1])` once. An awaitable result means the comparator is
  really async: await the trial (so no coroutine is left un-awaited and no
  `RuntimeWarning` fires) and hand the whole sort to `merge_sort`. A plain
  result gets the same `check_comparator_result_type` every other comparison
  gets, and the sort proceeds.
- **(rejected) Detect mid-sort and restart.** Have the `cmp_to_key` wrapper
  raise a private sentinel exception on the first awaitable, catch it around
  `arr.sort(...)`, and fall back to `merge_sort`. It avoids the extra call, but
  it has to `close()` the un-awaited coroutine from inside a sync key function,
  it re-runs every comparison already made, and it puts a `try`/`except` on the
  hot path to serve a case that is rare by construction.
- **(rejected) Narrow the contract for `sorted()` alone.** Documented as "a
  sync-signatured comparator returning a coroutine is unsupported in
  `sorted()`". This is the option the roadmap floated. It breaks the
  `callable-dispatch` spec's "Sync-signatured callable that returns a coroutine"
  scenario, which names no operation and therefore covers `sorted()`, and it
  breaks `test_sorted_sync_call_returning_coroutine_comparator` — which the
  batch's tripwire forbids touching.

**What the trial costs, stated plainly:** one extra comparator invocation per
comparator-based sort of two or more elements. It is a real, if minor,
observable difference for a comparator that counts its invocations — but no spec
and no test constrains the invocation count, and it could not: Timsort and merge
sort make different numbers of comparisons on the same input regardless. The
result of the trial is discarded rather than fed to the sort; threading it in
would mean reimplementing the sort.

`len(arr) > 1` guards the trial because a zero- or one-element buffer has no
pair to compare, and neither algorithm would invoke the comparator at all — so
the trial must not either.

### The per-comparison check is inlined, and calls out only to raise

```python
def _checked(comparator):
    def compare(a, b):
        sign = comparator(a, b)
        if type(sign) is not int:
            check_comparator_result_type(sign)
        return sign

    return compare
```

This is the `checked()` the benchmark measured (25.2 ms, 2.32x). The type test
is inlined and only the raising path calls out — the same trick
`is_new_extremum` already uses in this module and for the same reason: it sits
on a path taken O(n log n) times. Delegating unconditionally to
`check_comparator_result_type` measured slower there and would here.

The 3.6x row of the proposal's table is what handing the raw comparator to
`cmp_to_key` would buy. It is not available: `comparator-contract`'s
"sorted() rejects a bool comparator" scenario requires `TypeError`, `bool`
values compare fine under `cmp_to_key` (a bool is an int), and the sort would
silently produce a wrong order instead of raising. **1.3x is the price of the
contract, and the contract wins.**

### `reverse` handling does not move

`_SortedSink.end()` keeps sorting ascending and then walking `reversed(cache)`,
rather than passing `reverse=True` to `list.sort`. They are not the same for
tied elements — `list.sort(reverse=True)` is stable and keeps tied elements in
encounter order, while `reversed()` flips them — and the current behaviour is
`reversed()` on both the comparator and the no-comparator branch. Changing it
would be an observable ordering change smuggled into a performance story.

### Stability is preserved

`merge_sort`'s `_merge` takes from `left` on `sign <= 0`, which is stable.
Timsort is stable. `test_sorted_comparator_matches_cmp_to_key` is a property
test asserting exactly `sorted(values, key=cmp_to_key(cmp))`, so any stability
divergence fails the suite without a new test.

## Risks / Trade-offs

- **A comparator that counts invocations sees one more call.** → No spec or test
  constrains the count, and it cannot be constrained while two algorithms are in
  play. Recorded here and in `sort()`'s docstring so it is a documented
  property, not a surprise.
- **`list.sort` leaves the list partially reordered if the comparator raises.**
  → The buffer is discarded on the exception path; nothing downstream reads it.
  `TypeError` still propagates out of `end()` before any element is pushed
  downstream, which is what "raised before any ordering result is returned"
  requires.
- **The trial comparison runs before the `bool` rejection would otherwise be
  reached.** → It raises the same `TypeError` from the same helper, just one
  comparison earlier. The tests assert the exception, not which comparison
  raised it.
- **`sort` is a slightly odd name in a module story 5 renames to
  `comparator.py`.** → Accepted for now: within `sort.py` it is the natural
  name, and story 5's job is to decide where sorting and comparator semantics
  each belong after the split. Flagged here so story 5 inherits the question
  rather than rediscovering it.
- **The benchmark gate could fail to reproduce on other interpreters.** → The
  win is algorithmic (C-level Timsort vs. an interpreted merge), so it is not
  version-fragile. The confirmation run is on the 3.14 leg, the same one that
  produced the figures.

## Migration Plan

None — private surface, no public API change, no data. Rollback is reverting the
two-file diff.
