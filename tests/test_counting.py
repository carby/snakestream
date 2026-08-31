import pytest

from snakestream.collector import Characteristics
from snakestream.collectors import counting
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


def test_counting_reports_unordered() -> None:
    assert Characteristics.UNORDERED in counting().characteristics


@pytest.mark.asyncio
async def test_counting_declaration_matches_behaviour_across_orderings() -> None:
    # given the same elements in two different orders
    forward = await Stream.of([1, 2, 3, 4]).collect(counting())
    backward = await Stream.of([4, 3, 2, 1]).collect(counting())

    # then the declaration UNORDERED makes holds: the results compare equal
    assert forward == backward
