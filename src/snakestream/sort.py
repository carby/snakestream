async def merge_sort(arr, comparator):
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
        if await comparator(left[i], right[j]) <= 0:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1

    result.extend(left[i:])
    result.extend(right[j:])
    return result
