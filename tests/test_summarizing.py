import pytest

from snakestream.collector import Characteristics
from snakestream.collectors import summarizing_double, summarizing_int, summarizing_long
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
    assert result.sum == 6.0
    assert isinstance(result.sum, float)
    assert result.min == 1.0
    assert isinstance(result.min, float)
    assert result.max == 3.0
    assert isinstance(result.max, float)


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


def test_summarizing_int_and_long_report_unordered() -> None:
    assert Characteristics.UNORDERED in summarizing_int(len).characteristics
    assert Characteristics.UNORDERED in summarizing_long(len).characteristics


def test_summarizing_double_does_not_report_unordered() -> None:
    # its sum accumulates in float, and SummaryStatistics compares by value
    # across every field, so that one field decides the whole result
    assert Characteristics.UNORDERED not in summarizing_double(len).characteristics


@pytest.mark.asyncio
async def test_summarizing_int_is_order_invariant_in_every_field() -> None:
    # given the same elements in two different orders
    forward = await Stream.of(["a", "bb", "ccc", "dddd"]).collect(summarizing_int(len))
    backward = await Stream.of(["dddd", "ccc", "bb", "a"]).collect(summarizing_int(len))

    # then the whole NamedTuple compares equal, which is the claim UNORDERED
    # makes, and every field is equal individually - including average, the one
    # field that divides
    assert forward == backward
    assert forward.min == backward.min
    assert forward.max == backward.max
    assert forward.average == backward.average
