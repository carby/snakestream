import asyncio

import pytest
from collections.abc import AsyncGenerator

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
async def test_find_first_on_unordered_parallel_stream_still_finds_the_first() -> None:
    # given: the same reordering-pressure chain as the ordered test above, on
    # a stream declared unordered
    # when
    it = await Stream.of(values).parallel().unordered().map(_delay_by_position).find_first()

    # then: unordered() does not relax find_first(). Java's findFirst() finds
    # the leftmost element on an unordered parallel stream too - the javadoc
    # permits returning any element, the implementation declines to. A caller
    # who wants the race uses find_any().
    assert it == values[0]


@pytest.mark.asyncio
async def test_find_any_remains_the_unordered_alternative() -> None:
    # given
    seen = set()

    async def track_and_delay(n: int) -> int:
        seen.add(n)
        return await _delay_by_position(n)

    # when
    it = await Stream.of(values).parallel().map(track_and_delay).find_any()

    # then: find_any() still returns without a strictly ordered pull through
    # the whole source - not every element was necessarily visited
    assert it in values
    assert len(seen) < len(values)


@pytest.mark.asyncio
async def test_find_first_after_unordered_and_sorted_returns_the_smallest() -> None:
    # given: a source whose smallest element arrives last, so a racing drive
    # would surface a branch-local minimum instead. This is the regression
    # that motivated making ordering positional - before it, unordered() was
    # pipeline-wide, sorted() could not restore encounter order, and this
    # returned an arbitrary element.
    async def descending() -> AsyncGenerator[int, None]:
        for i in range(200, 0, -1):
            await asyncio.sleep(0)
            yield i

    # when: run repeatedly - the wrong answer was nondeterministic
    results = [await Stream.of(descending()).parallel().unordered().sorted(lambda a, b: a - b).find_first() for _ in range(10)]

    # then
    assert results == [1] * 10
