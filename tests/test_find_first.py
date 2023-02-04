import pytest

from snakestream import stream_of


@pytest.mark.asyncio
async def test_find_first() -> None:
    counter = 0

    def incr_counter(c):
        nonlocal counter
        counter += 1
        return c

    # when
    it = await stream_of([1, 2, 3, 4, 5, 6, 1, 2, 3, 4, 5, 6]) \
        .map(incr_counter) \
        .filter(lambda x: x == 6) \
        .find_first()

    # then
    assert it == 6
    assert counter == 6


@pytest.mark.asyncio
async def test_find_first_found_none() -> None:
    counter = 0

    def incr_counter(c):
        nonlocal counter
        counter += 1
        return c

    # when
    it = await stream_of([1, 2, 3, 4, 5, 6, 1, 2, 3, 4, 5, 6]) \
        .map(incr_counter) \
        .filter(lambda x: x == 100) \
        .find_first()

    # then
    assert it is None
    assert counter == 12
