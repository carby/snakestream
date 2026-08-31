import pytest

from snakestream.collector import Characteristics
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


def test_summing_int_and_long_report_unordered() -> None:
    assert Characteristics.UNORDERED in summing_int(len).characteristics
    assert Characteristics.UNORDERED in summing_long(len).characteristics


def test_summing_double_does_not_report_unordered() -> None:
    # float addition is not associative, so this one is order-sensitive in fact
    assert Characteristics.UNORDERED not in summing_double(len).characteristics


@pytest.mark.asyncio
async def test_summing_int_declaration_matches_behaviour_across_orderings() -> None:
    # given the same elements in two different orders
    forward = await Stream.of(["a", "bb", "ccc"]).collect(summing_int(len))
    backward = await Stream.of(["ccc", "bb", "a"]).collect(summing_int(len))

    # then the sums compare equal
    assert forward == backward
