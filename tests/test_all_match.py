import asyncio

import pytest

from snakestream import stream_of


@pytest.mark.asyncio
async def test_empty_stream() -> None:
    it = await stream_of([]) \
        .all_match(lambda x: x > 5)
    assert it is True


@pytest.mark.asyncio
async def test_none_matches() -> None:
    it = await stream_of([1, 2, 3, 2, 3, 1, 2]) \
        .all_match(lambda x: x > 5)
    assert it is False


@pytest.mark.asyncio
async def test_some_matches() -> None:
    it = await stream_of([1, 2, 3, 2, 3, 1, 2, 5, 6, 7]) \
        .all_match(lambda x: x < 5)
    assert it is False


@pytest.mark.asyncio
async def test_simple() -> None:
    it = await stream_of([1, 2, 3, 2, 3, 1, 2]) \
        .all_match(lambda x: x < 5)
    assert it is True


@pytest.mark.asyncio
async def test_simple_async() -> None:
    async def async_predicate(x: int) -> bool:
        await asyncio.sleep(0.01)
        return x < 5

    it = await stream_of([1, 2, 3, 2, 3, 1, 2]) \
        .all_match(async_predicate)
    assert it is True
