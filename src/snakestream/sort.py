from functools import cmp_to_key
from inspect import isawaitable
from typing import Any, cast
from collections.abc import Callable

from snakestream.callable_dispatch import is_async_callable
from snakestream.type import Comparator


def check_comparator_result_type(value: int) -> None:
    if type(value) is not int:
        raise TypeError(f"comparator must return an int (negative, zero, or positive), not {type(value).__name__}")


def is_new_extremum(sign: int, asc: bool) -> bool:
    """Whether an element that compared as `sign` against the currently-held
    extremum should displace it. The one home for the rule Stream.min()/max()
    and the min_by()/max_by() collectors both implement.

    comparator(element, found): negative if element orders before found,
    positive if after. found - the earlier element - is kept on a tie, which is
    what makes both forms first-of-tied-wins.

    Sync, and takes an already-awaited sign: it sits on the per-element path of
    both callers, so it replaces their existing check_comparator_result_type()
    call rather than adding a second one. The type test is inlined and only the
    raising path calls out, which keeps the success path at exactly the one
    call per element it cost before - delegating the check measured ~5%, and
    routing these terminals through a Collector instead cost +26% (see this
    change's design.md).
    """
    if type(sign) is not int:
        check_comparator_result_type(sign)
    return sign < 0 if asc else sign > 0


def _checked(comparator: Comparator) -> Callable[[Any, Any], int]:
    """A sync comparator wrapped so cmp_to_key cannot bypass the int contract.

    The type test is inlined and only the raising path calls out - the same
    trick is_new_extremum uses above, and for the same reason: cmp_to_key
    calls this O(n log n) times. Delegating unconditionally to
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
    if is_async_callable(comparator):
        return await merge_sort(arr, comparator)
    if len(arr) > 1:
        trial = comparator(arr[0], arr[1])
        if isawaitable(trial):
            await trial
            return await merge_sort(arr, comparator)
        check_comparator_result_type(cast("int", trial))
    arr.sort(key=cmp_to_key(_checked(comparator)))
    return arr


async def merge_sort(arr, comparator):
    # Reached only for a comparator sort() has already established returns
    # awaitables, so there is no classification left to make or share here.
    if len(arr) <= 1:
        return arr

    middle = len(arr) // 2
    left = await merge_sort(arr[:middle], comparator)
    right = await merge_sort(arr[middle:], comparator)

    return await _merge(left, right, comparator)


async def _merge(left, right, comparator):
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
