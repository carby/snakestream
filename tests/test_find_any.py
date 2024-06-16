import pytest

from snakestream import Stream


@pytest.mark.asyncio
async def test_find_any() -> None:
    counter = 0

    def incr_counter(c):
        nonlocal counter
        counter += 1
        return c

    # when
    it = await Stream.of([1, 2, 3, 4, 5, 6, 1, 2, 3, 4, 5, 6]) \
        .map(incr_counter) \
        .filter(lambda x: x == 6) \
        .find_any()

    # then
    assert it == 6
    assert counter == 6


@pytest.mark.asyncio
async def test_find_any_found_none() -> None:
    counter = 0

    def incr_counter(c):
        nonlocal counter
        counter += 1
        return c

    # when
    it = await Stream.of([1, 2, 3, 4, 5, 6, 1, 2, 3, 4, 5, 6]) \
        .map(incr_counter) \
        .filter(lambda x: x == 100) \
        .find_any()

    # then
    assert it is None
    assert counter == 12


@pytest.mark.asyncio
async def test_find_any_empty_stream() -> None:
    counter = 0

    def incr_counter(c):
        nonlocal counter
        counter += 1
        return c

    # when
    it = await Stream.of([]) \
        .map(incr_counter) \
        .find_any()

    # then
    assert it is None
    assert counter == 0
