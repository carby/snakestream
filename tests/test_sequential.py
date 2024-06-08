
import pytest
from snakestream.collector import to_list
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_sequential_simple(int_2_letter) -> None:
    # when
    it = await Stream.of([1, 2, 3, 4, 1, 2, 3, 4]) \
        .sequential() \
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
async def test_sequential_switch_to_parallel(int_2_letter) -> None:
    # when
    it = await Stream.of([1, 2, 3, 4, 1, 2, 3, 4]) \
        .parallel() \
        .map(lambda x: int_2_letter[x]) \
        .sequential() \
        .distinct() \
        .collect(to_list)
    # then
    assert 4 == len(it)
    assert 'a' in it
    assert 'b' in it
    assert 'c' in it
    assert 'd' in it
