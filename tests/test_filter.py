import pytest
import asyncio

from snakestream import Stream
from snakestream.collector import to_generator, to_list


@pytest.mark.asyncio
async def test_filter_multiple() -> None:
    # when
    it = Stream.of([1, 2, 3, 4, 5, 6]) \
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
async def test_filter_does_not_mutate_source() -> None:
    source = [1, 2, 3, 4, 5, 6]

    # when
    it = await Stream.of(source) \
        .filter(lambda x: x > 3) \
        .filter(lambda x: x < 6) \
        .collect(to_list)

    # then
    assert source != it
    assert len(source) == 6
    assert len(it) == 2


@pytest.mark.asyncio
async def test_filter_async_function() -> None:

    async def async_predicate(x: int) -> bool:
        await asyncio.sleep(0.01)
        return x < 3

    # when
    it = Stream.of([1, 2, 3, 4]) \
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
