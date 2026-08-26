import pytest
import asyncio

from snakestream import Stream
from snakestream.collector import to_generator
from snakestream.collectors import to_list
from snakestream.exception import StreamBuildException


async def async_flat_map(x: int) -> int:
    await asyncio.sleep(0.01)
    return x


@pytest.mark.asyncio
async def test_flat_map() -> None:
    # when
    it = Stream.of([[1, 2], [3, 4]]).flat_map(lambda x: Stream.of(x)).collect(to_generator)

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
async def test_flat_map_mixed_list() -> None:
    it = Stream.of([[1, 2], [3, 4], 5, [6, 7], 8]).flat_map(lambda x: Stream.of(x)).collect(to_generator)

    # then
    assert await it.__anext__() == 1
    assert await it.__anext__() == 2
    assert await it.__anext__() == 3
    assert await it.__anext__() == 4
    assert await it.__anext__() == 5
    assert await it.__anext__() == 6
    assert await it.__anext__() == 7
    assert await it.__anext__() == 8
    try:
        await it.__anext__()
    except StopAsyncIteration:
        pass
    else:
        assert False


@pytest.mark.asyncio
async def test_flat_map_closes_inner_generator_on_short_circuit() -> None:
    cleaned_up = []

    async def tracked_inner(n: int):
        try:
            for i in range(n):
                yield i
        finally:
            cleaned_up.append(n)

    def mapper(n: int) -> Stream:
        return Stream(tracked_inner(n))

    # when
    result = await Stream.of([5]).flat_map(mapper).limit(1).collect(to_list())

    # then
    assert result == [0]
    assert cleaned_up == [5]


@pytest.mark.asyncio
async def test_flat_map_still_closes_inner_generator_on_normal_exhaustion() -> None:
    cleaned_up = []

    async def tracked_inner(n: int):
        try:
            for i in range(n):
                yield i
        finally:
            cleaned_up.append(n)

    def mapper(n: int) -> Stream:
        return Stream(tracked_inner(n))

    # when
    result = await Stream.of([2, 3]).flat_map(mapper).collect(to_list())

    # then
    assert result == [0, 1, 0, 1, 2]
    assert cleaned_up == [2, 3]


@pytest.mark.asyncio
async def test_flat_map_async_function() -> None:
    # when
    try:
        Stream.of([[1, 2], [3, 4], 5]).flat_map(async_flat_map).collect(to_generator)
    except StreamBuildException:
        pass
    else:
        assert False
