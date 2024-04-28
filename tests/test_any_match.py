import asyncio

import pytest

from snakestream import Stream


@pytest.mark.asyncio
async def test_empty_stream() -> None:
    it = await Stream.of([]) \
        .any_match(lambda x: x > 5)
    assert it is False


@pytest.mark.asyncio
async def test_none_matches() -> None:
    it = await Stream.of([1, 2, 3, 2, 3, 1, 2]) \
        .any_match(lambda x: x > 5)
    assert it is False


@pytest.mark.asyncio
async def test_all_matches() -> None:
    it = await Stream.of([1, 2, 3, 2, 3, 1, 4, 5]) \
        .any_match(lambda x: x < 5)
    assert it is True


@pytest.mark.asyncio
async def test_simple() -> None:
    it = await Stream.of([1, 2, 3, 2, 3, 1, 2, 5, 6, 7]) \
        .any_match(lambda x: x < 5)
    assert it is True


@pytest.mark.asyncio
async def test_simple_async() -> None:
    async def async_predicate(x: int) -> bool:
        await asyncio.sleep(0.01)
        return x < 5

    it = await Stream.of([1, 2, 3, 2, 3, 1, 2, 5, 6, 7]) \
        .any_match(async_predicate)
    assert it is True
