from inspect import isawaitable

from snakestream.callable_dispatch import is_async_callable


def check_comparator_result_type(value: int) -> None:
    if type(value) is not int:
        raise TypeError(f"comparator must return an int (negative, zero, or positive), not {type(value).__name__}")


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
