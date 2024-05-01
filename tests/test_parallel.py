import time
import pytest
import asyncio

from snakestream import Stream
from snakestream.collector import to_list


@pytest.mark.asyncio
async def test_parallel_simple(int_2_letter) -> None:
    # when
    it = await Stream.of([1, 2, 3, 4, 1, 2, 3, 4]) \
        .parallel() \
        .map(lambda x: int_2_letter[x]) \
        .distinct() \
        .collect(to_list)
    # then
    assert 4 == len(it)
    assert 'a' in it
    assert 'b' in it
    assert 'c' in it
    assert 'd' in it


@pytest.mark.asyncio
async def test_parallel_is_faster_than_sequential() -> None:

    async def sleep(n):
        await asyncio.sleep(0.1)

    # when
    start_parallel = time.time()
    await Stream.of([1, 2, 3, 4, 1, 2, 3, 4]) \
        .parallel() \
        .map(sleep) \
        .distinct() \
        .collect(to_list)
    end_parallel = time.time()
    time_parallel = end_parallel - start_parallel

    start_sequential = time.time()
    await Stream.of([1, 2, 3, 4, 1, 2, 3, 4]) \
        .map(sleep) \
        .distinct() \
        .collect(to_list)
    end_sequential = time.time()
    time_sequential = end_sequential - start_sequential

    # then
    # usually something like 0,2 compared to 0.8
    assert (time_parallel) < (time_sequential)


@pytest.mark.asyncio
async def test_sequential_switch_to_sequential(int_2_letter) -> None:
    # when
    it = await Stream.of([1, 2, 3, 4, 1, 2, 3, 4]) \
        .sequential() \
        .map(lambda x: int_2_letter[x]) \
        .parallel() \
        .distinct() \
        .collect(to_list)
    # then
    assert 4 == len(it)
    assert 'a' in it
    assert 'b' in it
    assert 'c' in it
    assert 'd' in it
