import pytest

from snakestream.collectors import summing_double, summing_int, summing_long
from snakestream.stream import Stream


async def _async_len(s: str) -> int:
    return len(s)


@pytest.mark.asyncio
async def test_summing_int_sums_mapped_values() -> None:
    # when
    result = await Stream.of(["a", "bb", "ccc"]).collect(summing_int(len))

    # then
    assert result == 6


@pytest.mark.asyncio
async def test_summing_int_async_mapper() -> None:
    # when
    result = await Stream.of(["a", "bb", "ccc"]).collect(summing_int(_async_len))

    # then
    assert result == 6


@pytest.mark.asyncio
async def test_summing_int_empty_stream() -> None:
    # when
    result = await Stream.of([]).collect(summing_int(len))

    # then
    assert result == 0


@pytest.mark.asyncio
async def test_summing_long_sums_mapped_values() -> None:
    # when
    result = await Stream.of(["a", "bb", "ccc"]).collect(summing_long(len))

    # then
    assert result == 6


@pytest.mark.asyncio
async def test_summing_long_async_mapper() -> None:
    # when
    result = await Stream.of(["a", "bb", "ccc"]).collect(summing_long(_async_len))

    # then
    assert result == 6


@pytest.mark.asyncio
async def test_summing_long_empty_stream() -> None:
    # when
    result = await Stream.of([]).collect(summing_long(len))

    # then
    assert result == 0


@pytest.mark.asyncio
async def test_summing_double_sums_as_float() -> None:
    # when
    result = await Stream.of([1, 2, 3]).collect(summing_double(lambda x: x))

    # then
    assert result == 6.0
    assert isinstance(result, float)


@pytest.mark.asyncio
async def test_summing_double_async_mapper() -> None:
    async def double(x: int) -> int:
        return x

    # when
    result = await Stream.of([1, 2, 3]).collect(summing_double(double))

    # then
    assert result == 6.0
    assert isinstance(result, float)


@pytest.mark.asyncio
async def test_summing_double_empty_stream() -> None:
    # when
    result = await Stream.of([]).collect(summing_double(lambda x: x))

    # then
    assert result == 0.0
