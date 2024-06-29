from typing import AsyncGenerator
import pytest

from snakestream import Stream
from snakestream.collector import to_list, to_generator


async def async_generator() -> AsyncGenerator:
    for i in range(1, 6):
        yield i


@pytest.mark.asyncio
async def test_to_list_simple() -> None:
    # when
    actual = await to_list(async_generator())
    # then
    assert [1, 2, 3, 4, 5] == actual


@pytest.mark.asyncio
async def test_to_generator_simple() -> None:
    # when
    actual = to_generator(async_generator())
    # then
    assert await actual.__anext__() == 1
    assert await actual.__anext__() == 2
    assert await actual.__anext__() == 3
    assert await actual.__anext__() == 4
    assert await actual.__anext__() == 5

    with pytest.raises(StopAsyncIteration):
        await actual.__anext__()


@pytest.mark.asyncio
async def test_to_generator() -> None:
    # when
    it = Stream.of([1, 2, 3, 4]) \
        .collect(to_generator)
    # then
    assert await it.__anext__() == 1
    assert await it.__anext__() == 2
    assert await it.__anext__() == 3
    assert await it.__anext__() == 4

    with pytest.raises(StopAsyncIteration):
        await it.__anext__()


@pytest.mark.asyncio
async def test_to_generator_with_null_in_stream() -> None:
    # when
    it = Stream.of([1, 2, None, 4]) \
        .collect(to_generator)
    # then
    assert await it.__anext__() == 1
    assert await it.__anext__() == 2
    assert await it.__anext__() is None
    assert await it.__anext__() == 4

    with pytest.raises(StopAsyncIteration):
        await it.__anext__()


@pytest.mark.asyncio
async def test_to_generator_with_empty_list_input() -> None:
    # when
    it = Stream.of([]) \
        .collect(to_generator)
    # then
    with pytest.raises(StopAsyncIteration):
        await it.__anext__()


@pytest.mark.asyncio
async def test_to_list() -> None:
    # when
    it = await Stream.of([1, 2, 3, 4]) \
        .collect(to_list)
    # then
    assert it == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_to_list_with_none_in_stream() -> None:
    # when
    it = await Stream.of([1, None, 3, 4]) \
        .collect(to_list)
    # then
    assert it == [1, None, 3, 4]


@pytest.mark.asyncio
async def test_to_list_with_empty_list_input() -> None:
    # when
    it = await Stream.of([]) \
        .collect(to_list)
    # then
    assert it == []
