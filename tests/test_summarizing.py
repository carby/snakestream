import pytest

from snakestream.collector import summarizing_double, summarizing_int, summarizing_long
from snakestream.stream import Stream


async def _async_len(s: str) -> int:
    return len(s)


@pytest.mark.asyncio
async def test_summarizing_int_basic_values() -> None:
    # when
    result = await Stream.of(["a", "bb", "ccc"]).collect(summarizing_int(len))

    # then
    assert result.count == 3
    assert result.sum == 6
    assert result.min == 1
    assert result.max == 3
    assert result.average == 2.0


@pytest.mark.asyncio
async def test_summarizing_long_matches_summarizing_int() -> None:
    # when
    long_result = await Stream.of([1, 2, 3]).collect(summarizing_long(lambda x: x))
    int_result = await Stream.of([1, 2, 3]).collect(summarizing_int(lambda x: x))

    # then
    assert long_result == int_result


@pytest.mark.asyncio
async def test_summarizing_double_coerces_to_float() -> None:
    # when
    result = await Stream.of([1, 2, 3]).collect(summarizing_double(lambda x: x))

    # then
    assert result.sum == 6.0 and isinstance(result.sum, float)
    assert result.min == 1.0 and isinstance(result.min, float)
    assert result.max == 3.0 and isinstance(result.max, float)


@pytest.mark.asyncio
async def test_summarizing_int_async_mapper() -> None:
    # when
    result = await Stream.of(["a", "bb", "ccc"]).collect(summarizing_int(_async_len))

    # then
    assert result.sum == 6


@pytest.mark.asyncio
async def test_summarizing_int_empty_stream() -> None:
    # when
    result = await Stream.of([]).collect(summarizing_int(len))

    # then
    assert result.count == 0
    assert result.sum == 0
    assert result.min is None
    assert result.max is None
    assert result.average == 0.0
