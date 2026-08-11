import pytest
from hypothesis import given
from hypothesis import strategies as st

from snakestream import Stream
from snakestream.collector import to_list
from conftest import MyObject


@pytest.mark.asyncio
async def test_unique() -> None:
    # when
    it = await Stream.of([1, 7, 3, 7, 5, 6, 0, 6, 6]).distinct().collect(to_list)
    # then
    assert it == [1, 7, 3, 5, 6, 0]


@pytest.mark.asyncio
async def test_unique_empty_list() -> None:
    # when
    it = await Stream.of([]).distinct().collect(to_list)
    # then
    assert it == []


@pytest.mark.asyncio
async def test_unique_list_with_no_dupes() -> None:
    # when
    it = await Stream.of([1, 2, 3, 4]).distinct().collect(to_list)
    # then
    assert it == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_unique_object_list() -> None:
    # when
    input_list = [
        MyObject(1, "object1"),
        MyObject(2, "object2"),
        MyObject(3, "object3"),
        MyObject(2, "object2"),
        MyObject(3, "object3"),
    ]
    it = await Stream.of(input_list).distinct().collect(to_list)
    # then
    assert it == [MyObject(1, "object1"), MyObject(2, "object2"), MyObject(3, "object3")]


def _first_seen_order_dedup(values: list[int]) -> list[int]:
    return list(dict.fromkeys(values))


@given(values=st.lists(st.integers()))
@pytest.mark.asyncio
async def test_distinct_matches_first_seen_order_dedup(values: list[int]) -> None:
    # when
    actual = await Stream.of(values).distinct().collect(to_list)

    # then
    assert actual == _first_seen_order_dedup(values)
    assert len(actual) == len(set(actual))
