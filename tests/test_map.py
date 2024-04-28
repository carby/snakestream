import pytest

from snakestream import Stream
from snakestream.collector import to_generator, to_list


@pytest.mark.asyncio
async def test_map(int_2_letter) -> None:
    # when
    it = Stream.of([1, 2, 3, 4]) \
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
async def test_map_async_function(async_int_to_letter) -> None:
    async_int_to_letter = await async_int_to_letter

    # when
    it = Stream.of([1, 2, 3, 4]) \
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


@pytest.mark.asyncio
async def test_map_does_not_mutate_source(int_2_letter) -> None:
    source = [1, 2, 3, 4]

    # when
    it = await Stream.of(source) \
        .map(lambda x: int_2_letter[x]) \
        .collect(to_list)

    # then
    assert source != it
    assert len(source) == 4
    assert len(it) == 4
