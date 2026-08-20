import pytest

from snakestream.collector import collecting_and_then, counting, summing_int, to_list
from snakestream.exception import StreamBuildException
from snakestream.stream import Stream


async def _async_len(xs: list) -> int:
    return len(xs)


@pytest.mark.asyncio
async def test_collecting_and_then_applies_finisher() -> None:
    # when
    result = await Stream.of([1, 2, 3]).collect(collecting_and_then(to_list, tuple))

    # then
    assert result == (1, 2, 3)


@pytest.mark.asyncio
async def test_collecting_and_then_async_finisher() -> None:
    # when
    result = await Stream.of([1, 2, 3]).collect(collecting_and_then(to_list, _async_len))

    # then
    assert result == 3


@pytest.mark.asyncio
async def test_collecting_and_then_composes_with_downstream_finisher() -> None:
    # when
    result = await Stream.of([1, 2, 3]).collect(collecting_and_then(counting(), lambda n: n * 10))

    # then
    assert result == 30


@pytest.mark.asyncio
async def test_collecting_and_then_empty_stream() -> None:
    # when
    result = await Stream.of([]).collect(collecting_and_then(to_list, tuple))

    # then
    assert result == ()


@pytest.mark.asyncio
async def test_collecting_and_then_with_async_downstream_accumulator() -> None:
    # when
    result = await Stream.of([1, 2, 3]).collect(collecting_and_then(summing_int(lambda x: x), lambda n: n * 10))

    # then
    assert result == 60


@pytest.mark.asyncio
async def test_collecting_and_then_rejects_non_collector_downstream() -> None:
    async def not_a_collector(composition):
        return [x async for x in composition]

    with pytest.raises(StreamBuildException):
        collecting_and_then(not_a_collector, tuple)
