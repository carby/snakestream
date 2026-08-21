import pytest

from snakestream.collector import counting, mapping, summing_int, to_list
from snakestream.exception import StreamBuildException
from snakestream.stream import Stream


async def _async_double(x: int) -> int:
    return x * 2


@pytest.mark.asyncio
async def test_mapping_collects_mapped_values() -> None:
    # when
    result = await Stream.of(["a", "bb", "ccc"]).collect(mapping(len, to_list()))

    # then
    assert result == [1, 2, 3]


@pytest.mark.asyncio
async def test_mapping_async_mapper() -> None:
    # when
    result = await Stream.of([1, 2, 3]).collect(mapping(_async_double, to_list()))

    # then
    assert result == [2, 4, 6]


@pytest.mark.asyncio
async def test_mapping_empty_stream() -> None:
    # when
    result = await Stream.of([]).collect(mapping(len, to_list()))

    # then
    assert result == []


@pytest.mark.asyncio
async def test_mapping_composes_with_reducing_downstream() -> None:
    # when
    result = await Stream.of(["a", "bb", "ccc"]).collect(mapping(len, counting()))

    # then
    assert result == 3


@pytest.mark.asyncio
async def test_mapping_with_async_downstream_accumulator() -> None:
    # when
    result = await Stream.of(["a", "bb", "ccc"]).collect(mapping(len, summing_int(lambda x: x)))

    # then
    assert result == 6


@pytest.mark.asyncio
async def test_mapping_rejects_non_collector_downstream() -> None:
    async def not_a_collector(composition):
        return [x async for x in composition]

    with pytest.raises(StreamBuildException):
        mapping(len, not_a_collector)
