import pytest

from snakestream.collector import counting
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_counting_non_empty_stream() -> None:
    # when
    result = await Stream.of([1, 2, 3]).collect(counting())

    # then
    assert result == 3


@pytest.mark.asyncio
async def test_counting_empty_stream() -> None:
    # when
    result = await Stream.of([]).collect(counting())

    # then
    assert result == 0
