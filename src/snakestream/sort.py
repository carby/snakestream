from inspect import isawaitable

from snakestream.callable_dispatch import is_async_callable


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


async def merge_sort(arr, comparator):
    # state[0] = is_async, state[1] = checked; a shared mutable list so the
    # classification made in one _merge call is visible to every other
    # _merge call in this merge_sort run, not just recursive callees.
    state = [is_async_callable(comparator), False]
    return await _merge_sort(arr, comparator, state)


async def _merge_sort(arr, comparator, state):
    if len(arr) <= 1:
        return arr

    middle = len(arr) // 2
    left = await _merge_sort(arr[:middle], comparator, state)
    right = await _merge_sort(arr[middle:], comparator, state)

    return await _merge(left, right, comparator, state)


async def _merge(left, right, comparator, state):
    result = []
    i = 0
    j = 0
    while i < len(left) and j < len(right):
        sign = comparator(left[i], right[j])
        if state[0]:
            sign = await sign
        elif not state[1]:
            state[1] = True
            if isawaitable(sign):
                state[0] = True
                sign = await sign
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
