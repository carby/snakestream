import pytest

from snakestream.collector import Characteristics
from snakestream.collectors import _Box, counting
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_counting_non_empty_stream() -> None:
    # when
    result = await Stream([1, 2, 3]).collect(counting())

    # then
    assert result == 3


@pytest.mark.asyncio
async def test_counting_empty_stream() -> None:
    # when
    result = await Stream([]).collect(counting())

    # then
    assert result == 0


def test_counting_reports_unordered() -> None:
    assert Characteristics.UNORDERED in counting().characteristics


@pytest.mark.asyncio
async def test_counting_declaration_matches_behaviour_across_orderings() -> None:
    # given the same elements in two different orders
    forward = await Stream([1, 2, 3, 4]).collect(counting())
    backward = await Stream([4, 3, 2, 1]).collect(counting())

    # then the declaration UNORDERED makes holds: the results compare equal
    assert forward == backward


def test_box_holds_the_value_it_is_given_and_instances_are_independent() -> None:
    first = _Box(0)
    second = _Box(0)

    assert first.value == 0
    assert second.value == 0

    first.value += 1

    assert first.value == 1
    assert second.value == 0
    assert _Box(7).value == 7
