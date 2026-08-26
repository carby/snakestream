import pytest

from snakestream.collectors import averaging_double, averaging_int, averaging_long
from snakestream.stream import Stream


async def _async_identity(x: int) -> int:
    return x


@pytest.mark.asyncio
async def test_averaging_int_computes_mean() -> None:
    # when
    result = await Stream.of([1, 2, 3, 4]).collect(averaging_int(lambda x: x))

    # then
    assert result == 2.5


@pytest.mark.asyncio
async def test_averaging_int_async_mapper() -> None:
    # when
    result = await Stream.of([1, 2, 3, 4]).collect(averaging_int(_async_identity))

    # then
    assert result == 2.5


@pytest.mark.asyncio
async def test_averaging_int_empty_stream() -> None:
    # when
    result = await Stream.of([]).collect(averaging_int(lambda x: x))

    # then
    assert result == 0.0


@pytest.mark.asyncio
async def test_averaging_long_computes_mean() -> None:
    # when
    result = await Stream.of([1, 2, 3, 4]).collect(averaging_long(lambda x: x))

    # then
    assert result == 2.5


@pytest.mark.asyncio
async def test_averaging_long_async_mapper() -> None:
    # when
    result = await Stream.of([1, 2, 3, 4]).collect(averaging_long(_async_identity))

    # then
    assert result == 2.5


@pytest.mark.asyncio
async def test_averaging_long_empty_stream() -> None:
    # when
    result = await Stream.of([]).collect(averaging_long(lambda x: x))

    # then
    assert result == 0.0


@pytest.mark.asyncio
async def test_averaging_double_computes_mean() -> None:
    # when
    result = await Stream.of([1, 2, 3, 4]).collect(averaging_double(lambda x: x))

    # then
    assert result == 2.5


@pytest.mark.asyncio
async def test_averaging_double_async_mapper() -> None:
    # when
    result = await Stream.of([1, 2, 3, 4]).collect(averaging_double(_async_identity))

    # then
    assert result == 2.5


@pytest.mark.asyncio
async def test_averaging_double_empty_stream() -> None:
    # when
    result = await Stream.of([]).collect(averaging_double(lambda x: x))

    # then
    assert result == 0.0
