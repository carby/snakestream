# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name

import asyncio

from typing import AsyncGenerator
import pytest

from snakestream import stream
from snakestream.collector import to_generator, to_list
from snakestream.exception import StreamBuildException

int_2_letter = {
    1: 'a',
    2: 'b',
    3: 'c',
    4: 'd',
    5: 'e',
}

letter_2_int = {v: k for k, v in int_2_letter.items()}

coords = [
    {'x': 1, 'y': 5},
    {'x': 2, 'y': 6},
    {'x': 3, 'y': 7},
]


class MyObject:
    def __init__(self, identifier, name):
        self.id = identifier
        self.name = name

    def __eq__(self, other):
        if isinstance(other, MyObject):
            return self.id == other.id and self.name == other.name
        return False

    def __hash__(self):
        return hash((self.id, self.name))


async def async_generator() -> AsyncGenerator:
    for i in range(1, 6):
        yield i


async def async_int_to_letter(x: int) -> str:
    await asyncio.sleep(0.01)
    return int_2_letter[x]


async def async_flat_map(x: int) -> int:
    await asyncio.sleep(0.01)
    return x


async def async_predicate(x: int) -> bool:
    await asyncio.sleep(0.01)
    return x < 3


class AsyncIteratorImpl:
    def __init__(self, end_range):
        self.end = end_range
        self.start = -1

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.start < self.end - 1:
            self.start += 1
            return self.start
        raise StopAsyncIteration


# INPUTS
@pytest.mark.asyncio
async def test_input_list() -> None:
    # when
    it = stream([1, 2, 3, 4]) \
        .collect(to_generator)
    # then
    assert await it.__anext__() == 1
    assert await it.__anext__() == 2
    assert await it.__anext__() == 3
    assert await it.__anext__() == 4
    try:
        await it.__anext__()
    except StopAsyncIteration:
        pass
    else:
        assert False


@pytest.mark.asyncio
async def test_input_async_generator() -> None:
    # when
    it = stream(async_generator()) \
        .collect(to_generator)

    # then
    assert await it.__anext__() == 1
    assert await it.__anext__() == 2
    assert await it.__anext__() == 3
    assert await it.__anext__() == 4
    assert await it.__anext__() == 5
    try:
        await it.__anext__()
    except StopAsyncIteration:
        pass
    else:
        assert False


@pytest.mark.asyncio
async def test_input_async_iterator() -> None:
    # when
    it = stream(AsyncIteratorImpl(5)) \
        .collect(to_generator)

    # then
    assert await it.__anext__() == 0
    assert await it.__anext__() == 1
    assert await it.__anext__() == 2
    assert await it.__anext__() == 3
    assert await it.__anext__() == 4
    try:
        await it.__anext__()
    except StopAsyncIteration:
        pass
    else:
        assert False


# FILTER
@pytest.mark.asyncio
async def test_filter_multiple() -> None:
    # when
    it = stream([1, 2, 3, 4, 5, 6]) \
        .filter(lambda x: x > 3) \
        .filter(lambda x: x < 6) \
        .collect(to_generator)

    # then
    assert await it.__anext__() == 4
    assert await it.__anext__() == 5
    try:
        await it.__anext__()
    except StopAsyncIteration:
        pass
    else:
        assert False


@pytest.mark.asyncio
async def test_filter_async_function() -> None:
    # when
    it = stream([1, 2, 3, 4]) \
        .filter(async_predicate) \
        .collect(to_generator)

    # then
    assert await it.__anext__() == 1
    assert await it.__anext__() == 2
    try:
        await it.__anext__()
    except StopAsyncIteration:
        pass
    else:
        assert False


# MAP
@pytest.mark.asyncio
async def test_map() -> None:
    # when
    it = stream([1, 2, 3, 4]) \
        .map(lambda x: int_2_letter[x]) \
        .collect(to_generator)

    # then
    assert await it.__anext__() == 'a'
    assert await it.__anext__() == 'b'
    assert await it.__anext__() == 'c'
    assert await it.__anext__() == 'd'
    try:
        await it.__anext__()
    except StopAsyncIteration:
        pass
    else:
        assert False


@pytest.mark.asyncio
async def test_map_async_function() -> None:
    # when
    it = stream([1, 2, 3, 4]) \
        .map(async_int_to_letter) \
        .collect(to_generator)

    # then
    assert await it.__anext__() == 'a'
    assert await it.__anext__() == 'b'
    assert await it.__anext__() == 'c'
    assert await it.__anext__() == 'd'
    try:
        await it.__anext__()
    except StopAsyncIteration:
        pass
    else:
        assert False


# FLAT MAP
@pytest.mark.asyncio
async def test_flat_map() -> None:
    # when
    it = stream([[1, 2], [3, 4]]) \
        .flat_map(lambda x: stream(x)) \
        .collect(to_generator)

    # then
    assert await it.__anext__() == 1
    assert await it.__anext__() == 2
    assert await it.__anext__() == 3
    assert await it.__anext__() == 4
    try:
        await it.__anext__()
    except StopAsyncIteration:
        pass
    else:
        assert False


@pytest.mark.asyncio
async def test_flat_map_no_mixed_list() -> None:
    it = stream([[1, 2], [3, 4], 5]) \
        .flat_map(lambda x: stream(x)) \
        .collect(to_generator)

    # then
    assert await it.__anext__() == 1
    assert await it.__anext__() == 2
    assert await it.__anext__() == 3
    assert await it.__anext__() == 4
    try:
        await it.__anext__()
    except TypeError:
        pass
    else:
        assert False


@pytest.mark.asyncio
async def test_flat_map_async_function() -> None:
    # when
    try:
        stream([[1, 2], [3, 4], 5]) \
            .flat_map(async_flat_map) \
            .collect(to_generator)
    except StreamBuildException:
        pass
    else:
        assert False


# SORTED
@pytest.mark.asyncio
async def test_sorted() -> None:
    outset = [1, 5, 3, 4, 5, 2]

    actual = await stream(outset) \
        .sorted() \
        .collect(to_list)

    assert sorted(outset) == actual


@pytest.mark.asyncio
async def test_sorted_reverse() -> None:
    outset = [1, 5, 3, 4, 5, 2]

    actual = await stream(outset) \
        .sorted(reverse=True) \
        .collect(to_list)

    assert sorted(outset, reverse=True) == actual


@pytest.mark.asyncio
async def test_sorted_comparator() -> None:
    outset = [
        {'x': 1, 'y': 5},
        {'x': 3, 'y': 7},
        {'x': 2, 'y': 6},
    ]

    def compare(a, b):
        if a['x'] > b['x']:
            return 1
        elif a['x'] < b['x']:
            return -1
        else:
            return 0

    actual = await stream(outset) \
        .sorted(comparator=compare) \
        .collect(to_list)

    assert sorted(outset, key=lambda x: x['x']) == actual


@pytest.mark.asyncio
async def test_sorted_async_comparator_and_reverse() -> None:
    outset = [
        {'x': 1, 'y': 5},
        {'x': 3, 'y': 7},
        {'x': 2, 'y': 6},
    ]

    async def compare_async(a, b):
        await asyncio.sleep(0.01)
        if a['x'] == b['x']:
            return 0
        elif a['x'] > b['x']:
            return 1
        else:
            return -1

    actual = await stream(outset) \
        .sorted(comparator=compare_async, reverse=True) \
        .collect(to_list)

    assert actual == [
        {'x': 3, 'y': 7},
        {'x': 2, 'y': 6},
        {'x': 1, 'y': 5},
    ]


# UNIQUE
@pytest.mark.asyncio
async def test_unique() -> None:
    # when
    it = await stream([1, 7, 3, 7, 5, 6, 0, 6, 6]) \
        .unique() \
        .collect(to_list)
    # then
    assert it == [1, 7, 3, 5, 6, 0]


@pytest.mark.asyncio
async def test_unique_empty_list() -> None:
    # when
    it = await stream([]) \
        .unique() \
        .collect(to_list)
    # then
    assert it == []


@pytest.mark.asyncio
async def test_unique_list_with_no_dupes() -> None:
    # when
    it = await stream([1, 2, 3, 4]) \
        .unique() \
        .collect(to_list)
    # then
    assert it == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_unique_object_list() -> None:
    # when
    input_list = [MyObject(1, "object1"), MyObject(2, "object2"), MyObject(3, "object3"), MyObject(2, "object2"),
                  MyObject(3, "object3")]
    it = await stream(input_list) \
        .unique() \
        .collect(to_list)
    # then
    assert it == [MyObject(1, "object1"), MyObject(2, "object2"), MyObject(3, "object3")]


# REDUCE
@pytest.mark.asyncio
async def test_reducer() -> None:
    # when
    it = stream([1, 2, 3, 4, 5, 6]) \
        .reduce(0, lambda x, y: x + y)
    # then
    assert await it == 21


@pytest.mark.asyncio
async def test_reducer_mixed_chain() -> None:
    # when
    it = stream(['a', 'b', 'c', 'd']) \
        .map(lambda x: letter_2_int[x]) \
        .reduce(0, lambda x, y: x + y)
    # then
    assert await it == 10


# COLLECT
@pytest.mark.asyncio
async def test_collect_to_list() -> None:
    # when
    it = await stream([1, 2, 3, 4, 5, 6]) \
        .filter(lambda x: x > 3) \
        .filter(lambda x: x < 6) \
        .collect(to_list)

    # then
    assert it == [4, 5]


# FOR EACH
@pytest.mark.asyncio
async def test_for_each() -> None:
    def incr_y(c) -> None:
        c['y'] = 1

    await stream(coords) \
        .for_each(incr_y)

    assert coords[0]['y'] == 1
    assert coords[1]['y'] == 1
    assert coords[2]['y'] == 1


@pytest.mark.asyncio
async def test_for_each_async() -> None:
    async def async_incr_y(c) -> None:
        await asyncio.sleep(0.01)
        c['y'] = 1

    await stream(coords) \
        .for_each(async_incr_y)

    assert coords[0]['y'] == 1
    assert coords[1]['y'] == 1
    assert coords[2]['y'] == 1


# FIND FIRST
@pytest.mark.asyncio
async def test_find_first() -> None:
    counter = 0

    def incr_counter(c):
        nonlocal counter
        counter += 1
        return c

    # when
    it = await stream([1, 2, 3, 4, 5, 6, 1, 2, 3, 4, 5, 6]) \
        .map(incr_counter) \
        .filter(lambda x: x == 6) \
        .find_first()

    # then
    assert it == 6
    assert counter == 6


@pytest.mark.asyncio
async def test_find_first_found_none() -> None:
    counter = 0

    def incr_counter(c):
        nonlocal counter
        counter += 1
        return c

    # when
    it = await stream([1, 2, 3, 4, 5, 6, 1, 2, 3, 4, 5, 6]) \
        .map(incr_counter) \
        .filter(lambda x: x == 100) \
        .find_first()

    # then
    assert it is None
    assert counter == 12


# MAX
@pytest.mark.asyncio
async def test_find_max_value_normal_input():
    input_list = [1, 2, 3, 4, 5]
    # when
    it = await stream(input_list) \
        .max(lambda x, y: x > y)
    # then
    assert it == 5


@pytest.mark.asyncio
async def test_find_max_value_async_input():
    async def async_comparator(x: int, y: int) -> bool:
        await asyncio.sleep(0.01)
        return x > y

    input_list = [1, 2, 3, 4, 5]
    # when
    it = await stream(input_list) \
        .max(async_comparator)
    # then
    assert it == 5


@pytest.mark.asyncio
async def test_find_max_value_empty_input():
    input_list = []
    # when
    it = await stream(input_list) \
        .max(lambda x, y: x > y)
    # then
    assert it is None


@pytest.mark.asyncio
async def test_find_max_value_list_with_dupe_items():
    input_list = [1, 1, 2, 3, 4, 5]
    # when
    it = await stream(input_list) \
        .max(lambda x, y: x > y)
    # then
    assert it == 5

    input_list = [1, 2, 3, 4, 5, 5]
    # when
    it = await stream(input_list) \
        .max(lambda x, y: x > y)
    # then
    assert it == 5


@pytest.mark.asyncio
async def test_find_max_value_negative_values():
    input_list = [-1, -2, -3, -4, -5]
    # when
    it = await stream(input_list) \
        .max(lambda x, y: x > y)
    # then
    assert it == -1


@pytest.mark.asyncio
async def test_find_max_value_custom_comparator():
    input_list = ['a', 'bb', 'ccc']
    # when
    it = await stream(input_list) \
        .max(lambda x, y: len(x) > len(y))
    # then
    assert it == 'ccc'


@pytest.mark.asyncio
async def test_find_max_value_object_comparator() -> None:
    # when
    input_list = [MyObject(1, "object1"), MyObject(2, "object2"), MyObject(3, "object3"), MyObject(2, "object2"),
                  MyObject(3, "object3")]
    it = await stream(input_list) \
        .max(lambda x, y: x.id > y.id)
    # then
    assert it == MyObject(3, "object3")


# min
@pytest.mark.asyncio
async def test_find_min_value_normal_input():
    input_list = [1, 2, 3, 4, 5]
    # when
    it = await stream(input_list) \
        .min(lambda x, y: x > y)
    # then
    assert it == 1


@pytest.mark.asyncio
async def test_find_min_value_async_input():
    async def async_comparator(x: int, y: int) -> bool:
        await asyncio.sleep(0.01)
        return x > y

    input_list = [1, 2, 3, 4, 5]
    # when
    it = await stream(input_list) \
        .min(async_comparator)
    # then
    assert it == 1


@pytest.mark.asyncio
async def test_find_min_value_empty_input():
    input_list = []
    # when
    it = await stream(input_list) \
        .min(lambda x, y: x > y)
    # then
    assert it is None


@pytest.mark.asyncio
async def test_find_min_value_list_with_dupe_items():
    input_list = [1, 1, 2, 3, 4, 5]
    # when
    it = await stream(input_list) \
        .min(lambda x, y: x > y)
    # then
    assert it == 1

    input_list = [1, 2, 3, 4, 5, 5]
    # when
    it = await stream(input_list) \
        .min(lambda x, y: x > y)
    # then
    assert it == 1


@pytest.mark.asyncio
async def test_find_min_value_negative_values():
    input_list = [-1, -2, -3, -4, -5]
    # when
    it = await stream(input_list) \
        .min(lambda x, y: x > y)
    # then
    assert it == -5


@pytest.mark.asyncio
async def test_find_min_value_custom_comparator():
    input_list = ['a', 'bb', 'ccc']
    # when
    it = await stream(input_list) \
        .min(lambda x, y: len(x) > len(y))
    # then
    assert it == 'a'


@pytest.mark.asyncio
async def test_find_min_value_object_comparator() -> None:
    # when
    input_list = [MyObject(1, "object1"), MyObject(2, "object2"), MyObject(3, "object3"), MyObject(2, "object2"),
                  MyObject(3, "object3")]
    it = await stream(input_list) \
        .min(lambda x, y: x.id > y.id)
    # then
    assert it == MyObject(1, "object1")


# OTHER
@pytest.mark.asyncio
async def test_mixed_chain() -> None:
    # when
    it = stream([1, 2, 3, 4, 5, 6]) \
        .filter(lambda x: 3 < x < 6) \
        .map(lambda x: int_2_letter[x]) \
        .collect(to_generator)

    # then
    assert await it.__anext__() == 'd'
    assert await it.__anext__() == 'e'
    try:
        await it.__anext__()
    except StopAsyncIteration:
        pass
    else:
        assert False
