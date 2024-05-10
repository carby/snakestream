
import pytest

from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_is_parallel_parallel() -> None:
    # when
    res = Stream.of([1, 2, 3, 4, 1, 2, 3, 4]) \
        .parallel() \
        .distinct() \
        .is_parallel()
    # then
    assert res is True


@pytest.mark.asyncio
async def test_is_parallel_sequential() -> None:
    # when
    res = Stream.of([1, 2, 3, 4, 1, 2, 3, 4]) \
        .distinct() \
        .is_parallel()
    # then
    assert res is False
