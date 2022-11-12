import asyncio

import pytest

from snakestream.main import stream

int_2_letter = {
    1: 'a',
    2: 'b',
    3: 'c',
    4: 'd',
    5: 'e',
}


async def slow_predicate(x: int) -> bool:
    await asyncio.sleep(1)
    return x < 3


@pytest.mark.asyncio
async def test_chained_filters() -> None:
    # when
    it = stream([1, 2, 3, 4, 5, 6]) \
        .filter(lambda x: x > 3) \
        .filter(lambda x: x < 6) \
        .collect()
    # then
    assert(await it.__anext__() == 4)
    assert(await it.__anext__() == 5)
    try:
        await it.__anext__()
    except StopAsyncIteration:
        pass
    else:
        assert(1 == 0)


@pytest.mark.asyncio
async def test_map() -> None:
    # when
    it = stream([1, 2, 3, 4]) \
        .map(lambda x: int_2_letter[x]) \
        .collect()
    # then
    assert(await it.__anext__() == 'a')
    assert(await it.__anext__() == 'b')
    assert(await it.__anext__() == 'c')
    assert(await it.__anext__() == 'd')
    try:
        await it.__anext__()
    except StopAsyncIteration:
        pass
    else:
        assert(1 == 0)


@pytest.mark.asyncio
async def test_mixed_chain() -> None:
    # when
    it = stream([1, 2, 3, 4, 5, 6]) \
        .filter(lambda x: 3 < x < 6) \
        .map(lambda x: int_2_letter[x]) \
        .collect()
    # then
    assert(await it.__anext__() == 'd')
    assert(await it.__anext__() == 'e')
    try:
        await it.__anext__()
    except StopAsyncIteration:
        pass
    else:
        assert(1 == 0)

@pytest.mark.asyncio
async def test_async_function() -> None:
    # when
    it = stream([1, 2, 3, 4]) \
        .filter(slow_predicate) \
        .collect()

    # then
    assert(await it.__anext__() == 1)
    assert(await it.__anext__() == 2)
    try:
        await it.__anext__()
    except StopAsyncIteration:
        pass
    else:
        assert(1 == 0)
