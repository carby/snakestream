import asyncio

import pytest

from snakestream import stream_of


@pytest.mark.asyncio
async def test_reducer() -> None:
    # when
    it = stream_of([1, 2, 3, 4, 5, 6]) \
        .reduce(0, lambda x, y: x + y)
    # then
    assert await it == 21


@pytest.mark.asyncio
async def test_reducer_associative() -> None:
    # when
    it = stream_of([1, 2, 3, 4, 5, 6]) \
        .reduce(0, lambda x, y: x + y)

    it2 = stream_of([1, 2, 3, 4, 5, 6]) \
        .reduce(0, lambda x, y: y + x)
    # then
    assert await it == 21
    assert await it2 == 21


@pytest.mark.asyncio
async def test_async_reducer() -> None:
    async def async_reducer(x: int, y: int):
        await asyncio.sleep(0.01)
        return x + y

    # when
    it = stream_of([1, 2, 3, 4, 5, 6]) \
        .reduce(0, async_reducer)

    # then
    assert await it == 21


@pytest.mark.asyncio
async def test_reducer_mixed_chain(letter_2_int) -> None:
    # when
    it = stream_of(['a', 'b', 'c', 'd']) \
        .map(lambda x: letter_2_int[x]) \
        .reduce(0, lambda x, y: x + y)
    # then
    assert await it == 10
