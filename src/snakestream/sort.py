import asyncio
from functools import cmp_to_key
from inspect import isawaitable
from typing import Any, cast
from collections.abc import Callable

from snakestream.callable_dispatch import is_async_callable
from snakestream.comparator import KeyComparator, Segment, check_comparator_result_type
from snakestream.type import AsyncComparator, Comparator


def _checked(comparator: Comparator) -> Callable[[Any, Any], int]:
    """A sync comparator wrapped so cmp_to_key cannot bypass the int contract.

    The type test is inlined and only the raising path calls out - the same
    trick is_new_extremum uses in comparator.py, and for the same reason:
    cmp_to_key calls this O(n log n) times. Delegating unconditionally to
    check_comparator_result_type measured slower there and would here; keeping
    the check at all is what makes the sync fast path 2.3x rather than 3.6x.
    """

    def compare(a: Any, b: Any) -> int:
        sign = comparator(a, b)
        if type(sign) is not int:
            check_comparator_result_type(cast("int", sign))
        return cast("int", sign)

    return compare


async def sort(arr: list[Any], comparator: Comparator) -> list[Any]:
    """Sort by comparator, picking the algorithm the comparator allows.

    A sync comparator goes to list.sort() with cmp_to_key, i.e. Timsort in C;
    only an async one needs merge_sort's hand-written merge with an await in
    its inner loop. Measured 2.1x on 20,000 floats here, 1.8x end-to-end
    through sorted() once the pipeline's own per-element cost is counted.

    The sync path cannot hand cmp_to_key the raw comparator: comparator-contract
    makes sorted() responsible for raising TypeError on a bool result, and a
    bool compares perfectly well under cmp_to_key, so an unchecked sort would
    silently produce a wrong order instead. Hence _checked().

    The trial comparison settles callable-dispatch's one-time safety net before
    the sort rather than during it. A comparator with a plain `def __call__`
    returning a coroutine classifies as sync, and list.sort offers no
    per-comparison await to catch it in - so the check has to happen while
    there is still an await available. The trial is awaited before rerouting so
    no coroutine is left un-awaited. It costs one extra comparator invocation
    per comparator sort of two or more elements; nothing constrains the
    invocation count, and nothing could, since the two algorithms make
    different numbers of comparisons on the same input anyway.

    Returns the sorted list either way, though only merge_sort builds a new
    one - list.sort is in place, and unifying the signature is worth more than
    saving the rebind.
    """
    if isinstance(comparator, KeyComparator):
        return await _sort_by_key(arr, comparator.segments)
    if is_async_callable(comparator):
        return await merge_sort(arr, cast("AsyncComparator", comparator))
    if len(arr) > 1:
        trial = comparator(arr[0], arr[1])
        if isawaitable(trial):
            await trial
            return await merge_sort(arr, cast("AsyncComparator", comparator))
        check_comparator_result_type(cast("int", trial))
    arr.sort(key=cmp_to_key(_checked(comparator)))
    return arr


async def _column(extractor: Callable[[Any], Any], arr: list[Any]) -> list[Any]:
    """Extract one segment's key for every element, concurrently across
    elements. No cmp_to_key, no merge_sort, and no sign/bool validation -
    there is no comparator sign on this path, just a key.

    An async extractor's keys are gathered concurrently rather than awaited
    one at a time in a loop. Measured (design.md's open question, settled
    during implementation): an I/O-bound extractor (1ms sleep) sorting 1,000
    elements costs 1325ms sequential against 9ms gathered - concurrency is the
    whole point of an async key extractor, and a sequential loop was throwing
    it away. The one-time isawaitable safety net (a "sync" extractor whose
    plain def __call__ actually returns a coroutine) is a trial call on the
    first element - the same shape as sort()'s own trial comparison - but the
    coroutine it produces joins the gather instead of being discarded, so it
    costs no extra invocation.
    """
    if is_async_callable(extractor):
        return list(await asyncio.gather(*(extractor(element) for element in arr)))
    trial = extractor(arr[0])
    if isawaitable(trial):
        return list(await asyncio.gather(trial, *(extractor(element) for element in arr[1:])))
    return [trial, *(extractor(element) for element in arr[1:])]


class _Descending:  # noqa: PLW1641 - only ever compared inside a sort tuple, never hashed
    """Wraps a key so tuple comparison treats it as negated - the mixed-
    direction lane's only cost. `__lt__` and `__eq__` are the only dunders
    tuple comparison uses, so nothing else is needed. Paid only on the
    columns a chain marked descending, and only when the chain mixes
    directions: an all-ascending or all-descending chain never builds one.
    """

    __slots__ = ("key",)

    def __init__(self, key: Any) -> None:
        self.key = key

    def __lt__(self, other: "_Descending") -> bool:
        return other.key < self.key

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Descending) and other.key == self.key


async def _sort_by_key(arr: list[Any], segments: tuple[Segment, ...]) -> list[Any]:
    """Decorate-sort-undecorate: extract every segment's key once per
    element, sort on the keys alone, undecorate.

    Sorting on the key(s) alone (list.sort(key=...) over the paired list, not
    a bare (key, element) tuple sort) means Timsort's stability gives
    encounter order for equal keys for free, with no tie-break index needed,
    and that elements are never compared - only their keys - so an element
    that does not itself support < still sorts fine as long as its key does.

    A single ascending segment - what every pre-chaining `comparing()` call
    produces - takes today's exact path: one column, no tuple build, no outer
    gather, so add-comparator-comparing's measured figures stand unchanged.
    A single descending segment (only reachable via `reversed()`) adds
    `reverse=True`, which is comparator negation exactly (see below) rather
    than a second code path.

    Two or more segments extract their columns concurrently with each other
    via `asyncio.gather` - not just concurrently within a column - so a chain
    of k async extractors over n elements has k*n extractions in flight
    rather than k sequential rounds of n; this is the capability's main
    reason to exist. The columns zip into one tuple per element, and tuple
    comparison is lexicographic and short-circuits on the first unequal
    component in C, which is exactly tie-break semantics - so k segments still
    cost one Timsort pass, in one of three lanes:

    - all ascending: plain tuple sort.
    - all descending: `sort(reverse=True)`. CPython's sort is stable in the
      strong sense under `reverse=True` - equal elements keep their original
      relative order, it is not a post-hoc list reversal - so this equals
      comparator negation exactly, ties included.
    - mixed: only the descending columns are wrapped in `_Descending`, and
      the wrapped tuples sort ascending. This is the only lane that pays for
      a wrapper, and only on the columns that asked for one.

    Measured: a 2-segment chain sorting 20,000 `(int, int)` tuples costs
    ~12ms all-ascending against ~40ms with the second segment descending -
    roughly 3.3x, from `_Descending.__lt__`'s Python-level indirection
    replacing a plain tuple comparison in C on every element the earlier
    column ties on. Paid only in the mixed lane; both single-lane cases above
    stay in C throughout.
    """
    if not arr:
        return arr

    if len(segments) == 1:
        extractor, descending = segments[0]
        keys = await _column(extractor, arr)
        paired = sorted(zip(keys, arr, strict=True), key=lambda pair: pair[0], reverse=descending)
        return [element for _, element in paired]

    columns = await asyncio.gather(*(_column(extractor, arr) for extractor, _ in segments))
    directions = [descending for _, descending in segments]
    rows = zip(*columns, strict=True)

    if all(directions):
        paired = sorted(zip(rows, arr, strict=True), key=lambda pair: pair[0], reverse=True)
    elif not any(directions):
        paired = sorted(zip(rows, arr, strict=True), key=lambda pair: pair[0])
    else:
        wrapped = (tuple(_Descending(v) if d else v for v, d in zip(row, directions, strict=True)) for row in rows)
        paired = sorted(zip(wrapped, arr, strict=True), key=lambda pair: pair[0])

    return [element for _, element in paired]


async def merge_sort(arr: list[Any], comparator: AsyncComparator) -> list[Any]:
    # Reached only for a comparator sort() has already established returns
    # awaitables, so there is no classification left to make or share here.
    if len(arr) <= 1:
        return arr

    middle = len(arr) // 2
    left = await merge_sort(arr[:middle], comparator)
    right = await merge_sort(arr[middle:], comparator)

    return await _merge(left, right, comparator)


async def _merge(left: list[Any], right: list[Any], comparator: AsyncComparator) -> list[Any]:
    result = []
    i = 0
    j = 0
    while i < len(left) and j < len(right):
        sign = await comparator(left[i], right[j])
        check_comparator_result_type(sign)
        if sign <= 0:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1

    result.extend(left[i:])
    result.extend(right[j:])
    return result
