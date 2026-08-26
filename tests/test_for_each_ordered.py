import pytest
import asyncio

from snakestream import Stream


@pytest.mark.asyncio
async def test_for_each_ordered_sequential_preserves_order() -> None:
    # given
    seen = []

    # when
    await Stream.of([4, 1, 3, 2]).for_each_ordered(seen.append)

    # then
    assert seen == [4, 1, 3, 2]


@pytest.mark.asyncio
async def test_for_each_ordered_async_consumer() -> None:
    # given
    seen = []

    async def async_append(n) -> None:
        await asyncio.sleep(0.01)
        seen.append(n)

    # when
    await Stream.of([4, 1, 3, 2]).for_each_ordered(async_append)

    # then
    assert seen == [4, 1, 3, 2]


# A jumbled (non-ascending) source, so "encounter order" is visibly distinct
# from "sorted by value" - the guarantee under test is about position in the
# source, not value magnitude. Earlier positions get a longer processing
# delay than later ones, giving ParallelStream's racing branches real
# reordering pressure on the queued .map() step.
values = [4, 1, 7, 2, 8, 3, 6, 5]
delay_by_position = {value: (len(values) - position) * 0.02 for position, value in enumerate(values)}


async def _delay_by_position(n: int) -> int:
    await asyncio.sleep(delay_by_position[n])
    return n


@pytest.mark.asyncio
async def test_for_each_on_parallel_stream_can_be_out_of_order() -> None:
    # given: plain for_each on a ParallelStream makes no order guarantee,
    # and the map step's positional delay gives branches real reordering
    # pressure to race under
    seen: list[int] = []

    # when
    await Stream.of(values).parallel().map(_delay_by_position).for_each(seen.append)

    # then
    assert seen != values


@pytest.mark.asyncio
async def test_for_each_ordered_preserves_encounter_order_on_parallel_stream() -> None:
    # given: the same jumbled source, chain, and positional delay as above
    seen: list[int] = []

    # when
    await Stream.of(values).parallel().map(_delay_by_position).for_each_ordered(seen.append)

    # then: for_each_ordered still reports elements in source encounter
    # order despite being called on a ParallelStream with the same chain
    assert seen == values


@pytest.mark.asyncio
async def test_for_each_ordered_on_unordered_parallel_stream_delivers_every_element() -> None:
    # given: an unordered pipeline releases for_each_ordered() from the
    # encounter-order guarantee, so it runs under the stream's own executor
    # rather than forfeiting the concurrency the caller asked for - the same
    # split Java's ForEachOps makes between ForEachOrderedTask and ForEachTask
    seen: list[int] = []

    # when
    await Stream.of(values).parallel().unordered().map(_delay_by_position).for_each_ordered(seen.append)

    # then: every element exactly once, order unconstrained
    assert sorted(seen) == sorted(values)


@pytest.mark.asyncio
async def test_for_each_ordered_on_unordered_sequential_stream_still_delivers_in_order() -> None:
    # given: releasing the guarantee is not the same as scrambling - a
    # SEQUENTIAL stream has one worker, so it comes out in source order anyway
    seen: list[int] = []

    # when
    await Stream.of(values).unordered().for_each_ordered(seen.append)

    # then
    assert seen == values


@pytest.mark.asyncio
async def test_sorted_after_unordered_restores_the_for_each_ordered_guarantee() -> None:
    # given
    seen: list[int] = []

    # when
    await Stream.of(values).parallel().unordered().sorted(lambda a, b: a - b).for_each_ordered(seen.append)

    # then: sorted() set the ordering characteristic again, so the encounter
    # order for_each_ordered() honours is the sorted one
    assert seen == sorted(values)
