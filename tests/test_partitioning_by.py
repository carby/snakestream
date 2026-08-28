import asyncio

import pytest

from snakestream.collector import Characteristics
from snakestream.collectors import counting, mapping, partitioning_by, to_list, to_set
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


def test_partitioning_by_reports_unordered_with_an_unordered_downstream() -> None:
    assert Characteristics.UNORDERED in partitioning_by(lambda x: x % 2 == 0, to_set()).characteristics


def test_partitioning_by_does_not_report_unordered_with_an_ordered_downstream() -> None:
    assert Characteristics.UNORDERED not in partitioning_by(lambda x: x % 2 == 0, to_list()).characteristics


def test_partitioning_by_default_downstream_is_ordered() -> None:
    # the default collects each partition into a list, which observes order
    assert Characteristics.UNORDERED not in partitioning_by(lambda x: x % 2 == 0).characteristics


def test_partitioning_by_derivation_composes_through_nesting() -> None:
    assert Characteristics.UNORDERED in partitioning_by(lambda x: x % 2 == 0, mapping(str, to_set())).characteristics


@pytest.mark.asyncio
async def test_partitioning_by_keeps_its_two_keys_in_order_under_the_derivation() -> None:
    # given a populated stream and an empty one, since the keys are seeded in
    # the supplier and so must not depend on what arrives
    populated = await Stream.of([1, 2, 3]).collect(partitioning_by(lambda x: x % 2 == 0, to_set()))
    empty = await Stream.of([]).collect(partitioning_by(lambda x: x % 2 == 0, to_set()))

    # then both carry exactly the two keys, in that order
    assert list(populated.keys()) == [True, False]
    assert list(empty.keys()) == [True, False]
