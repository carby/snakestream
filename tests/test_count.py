import pytest

from snakestream import Stream


@pytest.mark.asyncio
async def test_empty_stream() -> None:
    it = await Stream.of([]) \
        .count()
    assert it == 0


@pytest.mark.asyncio
async def test_base_test() -> None:
    it = await Stream.of([1, 2, 3, 4, 5, 6]) \
        .count()
    assert it == 6


@pytest.mark.asyncio
async def test_case_insensitive() -> None:
    it = await Stream.of(['test', 'Test', 'test', 'foo', 'bar']) \
        .count()
    assert it == 5


@pytest.mark.asyncio
async def test_null_count() -> None:
    it = await Stream.of(['test', 'Test', 'test', None, 'bar']) \
        .count()
    assert it == 5
