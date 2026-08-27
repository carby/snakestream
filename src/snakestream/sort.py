import asyncio
from functools import cmp_to_key
from inspect import isawaitable
from typing import Any, cast
from collections.abc import Callable

from snakestream.callable_dispatch import is_async_callable
from snakestream.comparator import _KeyComparator, check_comparator_result_type
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
    if isinstance(comparator, _KeyComparator):
        return await _sort_by_key(arr, comparator.key_extractor)
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


async def _sort_by_key(arr: list[Any], key_extractor: Callable[[Any], Any]) -> list[Any]:
    """Decorate-sort-undecorate: extract each element's key once, sort on the
    key alone, undecorate. No cmp_to_key, no merge_sort, and no sign/bool
    validation - there is no comparator sign on this path, just a key.

    Sorting on the key alone (list.sort(key=...) over the paired list, not a
    bare (key, element) tuple sort) means Timsort's stability gives encounter
    order for equal keys for free, with no tie-break index needed, and that
    elements are never compared - only their keys - so an element that does
    not itself support < still sorts fine as long as its key does.

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
    if not arr:
        return arr
    if is_async_callable(key_extractor):
        keys = await asyncio.gather(*(key_extractor(element) for element in arr))
    else:
        trial = key_extractor(arr[0])
        if isawaitable(trial):
            keys = await asyncio.gather(trial, *(key_extractor(element) for element in arr[1:]))
        else:
            keys = [trial, *(key_extractor(element) for element in arr[1:])]

    paired = sorted(zip(keys, arr, strict=True), key=lambda pair: pair[0])
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
