import pytest
import asyncio

from snakestream import stream_of
from snakestream.collector import to_list


@pytest.mark.asyncio
async def test_sorted() -> None:
    outset = [1, 5, 3, 4, 5, 2]

    actual = await stream_of(outset) \
        .sorted() \
        .collect(to_list)

    assert sorted(outset) == actual


@pytest.mark.asyncio
async def test_sorted_reverse() -> None:
    outset = [1, 5, 3, 4, 5, 2]

    actual = await stream_of(outset) \
        .sorted(reverse=True) \
        .collect(to_list)

    assert sorted(outset, reverse=True) == actual


@pytest.mark.asyncio
async def test_sorted_comparator() -> None:
    outset = [
        {'x': 1, 'y': 5},
        {'x': 3, 'y': 7},
        {'x': 2, 'y': 6},
    ]

    def compare(a, b):
        if a['x'] > b['x']:
            return 1
        elif a['x'] < b['x']:
            return -1
        else:
            return 0

    actual = await stream_of(outset) \
        .sorted(comparator=compare) \
        .collect(to_list)

    assert sorted(outset, key=lambda x: x['x']) == actual


@pytest.mark.asyncio
async def test_sorted_async_comparator_and_reverse() -> None:
    outset = [
        {'x': 1, 'y': 5},
        {'x': 3, 'y': 7},
        {'x': 2, 'y': 6},
    ]

    async def compare_async(a, b):
        await asyncio.sleep(0.01)
        if a['x'] == b['x']:
            return 0
        elif a['x'] > b['x']:
            return 1
        else:
            return -1

    actual = await stream_of(outset) \
        .sorted(comparator=compare_async, reverse=True) \
        .collect(to_list)

    assert actual == [
        {'x': 3, 'y': 7},
        {'x': 2, 'y': 6},
        {'x': 1, 'y': 5},
    ]
