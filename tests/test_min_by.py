import asyncio

import pytest

from snakestream.collectors import min_by
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_min_by_selects_smallest_element() -> None:
    # when
    result = await Stream.of([3, 1, 2]).collect(min_by(lambda a, b: a - b))

    # then
    assert result == 1


@pytest.mark.asyncio
async def test_min_by_empty_stream_returns_none() -> None:
    # when
    result = await Stream.of([]).collect(min_by(lambda a, b: a - b))

    # then
    assert result is None


@pytest.mark.asyncio
async def test_min_by_keeps_first_of_tied_elements() -> None:
    input_list = [("a", 5), ("b", 5)]

    # when
    result = await Stream.of(input_list).collect(min_by(lambda x, y: x[1] - y[1]))

    # then
    assert result == ("a", 5)


@pytest.mark.asyncio
async def test_min_by_async_comparator_is_awaited() -> None:
    async def async_comparator(x: int, y: int) -> int:
        await asyncio.sleep(0.01)
        return x - y

    # when
    result = await Stream.of([3, 1, 2]).collect(min_by(async_comparator))

    # then
    assert result == 1


@pytest.mark.asyncio
async def test_min_by_rejects_bool_comparator() -> None:
    # when / then
    with pytest.raises(TypeError):
        await Stream.of([3, 1, 2]).collect(min_by(lambda x, y: x > y))
