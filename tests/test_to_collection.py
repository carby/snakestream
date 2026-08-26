import bisect

import pytest

from snakestream.collectors import to_collection
from snakestream.stream import Stream


class _SortedContainer:
    def __init__(self) -> None:
        self.items: list[int] = []

    def add(self, item: int) -> None:
        bisect.insort(self.items, item)


@pytest.mark.asyncio
async def test_to_collection_builds_a_set() -> None:
    # when
    result = await Stream.of([1, 2, 3]).collect(to_collection(set))

    # then
    assert result == {1, 2, 3}


@pytest.mark.asyncio
async def test_to_collection_supports_a_custom_container() -> None:
    # when
    result = await Stream.of([3, 1, 2]).collect(to_collection(_SortedContainer))

    # then
    assert result.items == [1, 2, 3]


@pytest.mark.asyncio
async def test_to_collection_each_call_gets_its_own_container() -> None:
    # given
    collector = to_collection(set)

    # when
    first = await Stream.of([1, 2]).collect(collector)
    second = await Stream.of([3, 4]).collect(collector)

    # then
    assert first == {1, 2}
    assert second == {3, 4}


@pytest.mark.asyncio
async def test_to_collection_empty_stream() -> None:
    # when
    result = await Stream.of([]).collect(to_collection(set))

    # then
    assert result == set()
