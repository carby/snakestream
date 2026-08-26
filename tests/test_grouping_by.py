import asyncio

import pytest

from snakestream.collectors import counting, grouping_by, joining
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
