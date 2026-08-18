import pytest

from snakestream.collector import to_set
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_to_set_builds_set_from_stream_elements() -> None:
    # when
    result = await Stream.of([1, 2, 2, 3]).collect(to_set())

    # then
    assert result == {1, 2, 3}


@pytest.mark.asyncio
async def test_to_set_empty_stream_returns_empty_set() -> None:
    # when
    result = await Stream.of([]).collect(to_set())

    # then
    assert result == set()
