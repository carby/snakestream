import asyncio

import pytest

from snakestream.collector import Characteristics
from snakestream.collectors import counting, grouping_by, joining, mapping, to_list, to_set
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_grouping_by_no_downstream_buckets_into_lists() -> None:
    # when
    result = await Stream.of([1, 2, 3, 4, 5]).collect(grouping_by(lambda x: x % 2))

    # then
    assert result == {1: [1, 3, 5], 0: [2, 4]}


@pytest.mark.asyncio
async def test_grouping_by_empty_stream_returns_empty_dict() -> None:
    # when
    result = await Stream.of([]).collect(grouping_by(lambda x: x))

    # then
    assert result == {}


@pytest.mark.asyncio
async def test_grouping_by_only_produced_keys_present() -> None:
    # when
    result = await Stream.of([1, 1, 1]).collect(grouping_by(lambda x: x))

    # then
    assert result == {1: [1, 1, 1]}


@pytest.mark.asyncio
async def test_grouping_by_async_classifier_is_awaited() -> None:
    async def async_classifier(x: int) -> int:
        await asyncio.sleep(0.01)
        return x % 2

    # when
    result = await Stream.of([1, 2, 3, 4, 5]).collect(grouping_by(async_classifier))

    # then
    assert result == {1: [1, 3, 5], 0: [2, 4]}


@pytest.mark.asyncio
async def test_grouping_by_with_counting_downstream() -> None:
    # when
    result = await Stream.of([1, 2, 3, 4, 5]).collect(grouping_by(lambda x: x % 2, counting()))

    # then
    assert result == {1: 3, 0: 2}


@pytest.mark.asyncio
async def test_grouping_by_with_joining_downstream() -> None:
    # when
    result = await Stream.of(["a", "bb", "ccc", "dd"]).collect(grouping_by(len, joining(", ")))

    # then
    assert result == {1: "a", 2: "bb, dd", 3: "ccc"}


@pytest.mark.asyncio
async def test_grouping_by_only_present_keys_get_downstream_reduced_entry() -> None:
    # when
    result = await Stream.of(["a", "bb", "bbb"]).collect(grouping_by(len, counting()))

    # then
    assert result == {1: 1, 2: 1, 3: 1}
    assert 4 not in result


def test_grouping_by_reports_unordered_with_an_unordered_downstream() -> None:
    assert Characteristics.UNORDERED in grouping_by(len, to_set()).characteristics


def test_grouping_by_does_not_report_unordered_with_an_ordered_downstream() -> None:
    assert Characteristics.UNORDERED not in grouping_by(len, to_list()).characteristics


def test_grouping_by_default_downstream_is_ordered() -> None:
    # the default collects each group into a list, which observes order
    assert Characteristics.UNORDERED not in grouping_by(len).characteristics


def test_grouping_by_derivation_composes_through_nesting() -> None:
    # derived through the adapter to the innermost downstream
    assert Characteristics.UNORDERED in grouping_by(len, mapping(str, to_set())).characteristics


@pytest.mark.asyncio
async def test_grouping_by_into_a_set_collects_equal_in_either_order() -> None:
    # given the same elements in two orders
    forward = [0, 8, 16, 24, 32]
    backward = list(reversed(forward))

    # when
    one = await Stream.of(forward).collect(grouping_by(lambda n: n % 3, to_set()))
    other = await Stream.of(backward).collect(grouping_by(lambda n: n % 3, to_set()))

    # then the declared characteristic is true of the behaviour
    assert one == other
