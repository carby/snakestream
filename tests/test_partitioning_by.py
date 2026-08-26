import asyncio

import pytest

from snakestream.collectors import counting, partitioning_by
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_partitioning_by_no_downstream_splits_into_lists() -> None:
    # when
    result = await Stream.of([1, 2, 3, 4, 5]).collect(partitioning_by(lambda x: x % 2 == 0))

    # then
    assert result == {True: [2, 4], False: [1, 3, 5]}


@pytest.mark.asyncio
async def test_partitioning_by_empty_stream_yields_both_keys_as_empty_lists() -> None:
    # when
    result = await Stream.of([]).collect(partitioning_by(lambda x: True))

    # then
    assert result == {True: [], False: []}


@pytest.mark.asyncio
async def test_partitioning_by_one_empty_partition_still_appears_as_key() -> None:
    # when
    result = await Stream.of([1, 2, 3]).collect(partitioning_by(lambda x: x > 100))

    # then
    assert result == {True: [], False: [1, 2, 3]}


@pytest.mark.asyncio
async def test_partitioning_by_async_predicate_is_awaited() -> None:
    async def async_predicate(x: int) -> bool:
        await asyncio.sleep(0.01)
        return x % 2 == 0

    # when
    result = await Stream.of([1, 2, 3, 4, 5]).collect(partitioning_by(async_predicate))

    # then
    assert result == {True: [2, 4], False: [1, 3, 5]}


@pytest.mark.asyncio
async def test_partitioning_by_with_counting_downstream() -> None:
    # when
    result = await Stream.of([1, 2, 3, 4, 5]).collect(partitioning_by(lambda x: x % 2 == 0, counting()))

    # then
    assert result == {True: 2, False: 3}


@pytest.mark.asyncio
async def test_partitioning_by_downstream_runs_on_empty_partition() -> None:
    # when
    result = await Stream.of([1, 3, 5]).collect(partitioning_by(lambda x: x % 2 == 0, counting()))

    # then
    assert result == {True: 0, False: 3}
