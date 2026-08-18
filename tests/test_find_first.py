import asyncio

import pytest

from snakestream import Stream


@pytest.mark.asyncio
async def test_find_first_returns_first_element() -> None:
    # when
    it = await Stream.of([4, 1, 3, 2]).find_first()

    # then
    assert it == 4


@pytest.mark.asyncio
async def test_find_first_empty_stream() -> None:
    # when
    it = await Stream.of([]).find_first()

    # then
    assert it is None


@pytest.mark.asyncio
async def test_find_first_only_pulls_first_element() -> None:
    # given
    seen = []

    def track(n):
        seen.append(n)
        return n

    # when
    it = await Stream.of([4, 1, 3, 2]).map(track).find_first()

    # then
    assert it == 4
    assert seen == [4]


# Same jumbled-source-with-positional-delay setup as
# tests/test_for_each_ordered.py, giving ParallelStream's racing branches
# real reordering pressure on the queued .map() step.
values = [4, 1, 7, 2, 8, 3, 6, 5]
delay_by_position = {value: (len(values) - position) * 0.02 for position, value in enumerate(values)}


async def _delay_by_position(n: int) -> int:
    await asyncio.sleep(delay_by_position[n])
    return n


@pytest.mark.asyncio
async def test_find_first_on_ordered_parallel_stream_returns_true_first_element() -> None:
    # when
    it = await Stream.of(values).parallel().map(_delay_by_position).find_first()

    # then: despite the first element having the longest delay, an ordered
    # ParallelStream still reports the true first-encounter-order element
    assert it == values[0]


@pytest.mark.asyncio
async def test_find_first_on_ordered_parallel_stream_empty_source() -> None:
    # when
    it = await Stream.of([]).parallel().find_first()

    # then
    assert it is None


@pytest.mark.asyncio
async def test_find_first_on_unordered_parallel_stream_races() -> None:
    # given: an unordered ParallelStream with the same reordering-pressure
    # chain as the ordered test above
    seen = set()

    async def track_and_delay(n: int) -> int:
        seen.add(n)
        return await _delay_by_position(n)

    # when
    it = await Stream.of(values).parallel().unordered().map(track_and_delay).find_first()

    # then: a match was found without waiting for a strictly ordered pull
    # through the whole source - not every element was necessarily visited
    assert it in values
    assert len(seen) < len(values)
