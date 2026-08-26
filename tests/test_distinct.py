import pytest
from hypothesis import given
from hypothesis import strategies as st

from snakestream import Stream
from snakestream.collectors import to_list
from conftest import MyObject


@pytest.mark.asyncio
async def test_unique() -> None:
    # when
    it = await Stream.of([1, 7, 3, 7, 5, 6, 0, 6, 6]).distinct().collect(to_list())
    # then
    assert it == [1, 7, 3, 5, 6, 0]


@pytest.mark.asyncio
async def test_unique_empty_list() -> None:
    # when
    it = await Stream.of([]).distinct().collect(to_list())
    # then
    assert it == []


@pytest.mark.asyncio
async def test_unique_list_with_no_dupes() -> None:
    # when
    it = await Stream.of([1, 2, 3, 4]).distinct().collect(to_list())
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
    it = await Stream.of(input_list).distinct().collect(to_list())
    # then
    assert it == [MyObject(1, "object1"), MyObject(2, "object2"), MyObject(3, "object3")]


def _first_seen_order_dedup(values: list[int]) -> list[int]:
    return list(dict.fromkeys(values))


@given(values=st.lists(st.integers()))
@pytest.mark.asyncio
async def test_distinct_matches_first_seen_order_dedup(values: list[int]) -> None:
    # when
    actual = await Stream.of(values).distinct().collect(to_list())

    # then
    assert actual == _first_seen_order_dedup(values)
    assert len(actual) == len(set(actual))


@pytest.mark.asyncio
async def test_distinct_state_not_shared_across_separate_streams() -> None:
    # given: a first stream consumes elements that would collide with a
    # second, independently-built distinct() stream if `seen` leaked
    await Stream.of([1, 2, 3]).distinct().collect(to_list())

    # when
    second = await Stream.of([1, 2, 3]).distinct().collect(to_list())

    # then
    assert second == [1, 2, 3]


@pytest.mark.asyncio
async def test_distinct_state_fresh_on_second_composition() -> None:
    # given
    stream = Stream.of([1, 2, 3]).distinct()
    first = await stream.collect(to_list())

    # when
    second = await stream.collect(to_list())

    # then
    assert first == [1, 2, 3]
    # source is exhausted after the first run, but a second composition must
    # not raise or silently reuse the first run's `seen` set
    assert second == []
