import pytest

from snakestream import stream_of
from snakestream.collector import to_list
from conftest import MyObject


@pytest.mark.asyncio
async def test_unique() -> None:
    # when
    it = await stream_of([1, 7, 3, 7, 5, 6, 0, 6, 6]) \
        .unique() \
        .collect(to_list)
    # then
    assert it == [1, 7, 3, 5, 6, 0]


@pytest.mark.asyncio
async def test_unique_empty_list() -> None:
    # when
    it = await stream_of([]) \
        .unique() \
        .collect(to_list)
    # then
    assert it == []


@pytest.mark.asyncio
async def test_unique_list_with_no_dupes() -> None:
    # when
    it = await stream_of([1, 2, 3, 4]) \
        .unique() \
        .collect(to_list)
    # then
    assert it == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_unique_object_list() -> None:
    # when
    input_list = [MyObject(1, "object1"), MyObject(2, "object2"), MyObject(3, "object3"), MyObject(2, "object2"),
                  MyObject(3, "object3")]
    it = await stream_of(input_list) \
        .unique() \
        .collect(to_list)
    # then
    assert it == [MyObject(1, "object1"), MyObject(2, "object2"), MyObject(3, "object3")]
