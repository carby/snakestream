# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name

import asyncio

from typing import AsyncGenerator
import pytest

from snakestream import stream
from snakestream.collectors import to_generator, to_list
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
