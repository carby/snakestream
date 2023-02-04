import pytest

from snakestream import stream_of
from snakestream.collector import to_list, to_generator


@pytest.mark.asyncio
async def test_to_generator() -> None:
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
async def test_to_generator_with_empty_list_input() -> None:
    # when
    it = stream_of([]) \
        .collect(to_generator)
    # then
    try:
        await it.__anext__()
    except StopAsyncIteration:
        pass
    else:
        assert False


@pytest.mark.asyncio
async def test_to_list() -> None:
    # when
    it = await stream_of([1, 2, 3, 4]) \
        .collect(to_list)
    # then
    assert it == [1, 2, 3, 4]


'''
@pytest.mark.asyncio
async def test_to_list_with_nulls() -> None:
    # when
    it = await stream([1, None, 3, 4]) \
        .collect(to_list)
    # then
    assert it == [1, 3, 4]
'''


@pytest.mark.asyncio
async def test_to_list_with_empty_list_input() -> None:
    # when
    it = await stream_of([]) \
        .collect(to_list)
    # then
    assert it == []
