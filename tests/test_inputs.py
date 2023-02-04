# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name

from typing import AsyncGenerator
import pytest

from snakestream import stream_of
from snakestream.collector import to_generator


async def async_generator() -> AsyncGenerator:
    for i in range(1, 6):
        yield i


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


@pytest.mark.asyncio
async def test_input_list() -> None:
    # when
    it = stream_of([1, 2, 3, 4]) \
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
    it = stream_of(async_generator()) \
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
    it = stream_of(AsyncIteratorImpl(5)) \
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
