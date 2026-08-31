import pytest
import asyncio
import time

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
    # encounter-order guarantee, so no delivery barrier is engaged and nothing
    # is held back waiting for an earlier element - the same split Java's
    # ForEachOps makes between ForEachOrderedTask and ForEachTask. Both cases
    # run under the stream's own executor; the barrier is the only difference
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
async def test_for_each_ordered_on_unordered_parallel_stream_does_not_deliver_in_order() -> None:
    # given the same unordered pipeline as above. The test above pins that
    # every element arrives; this one pins that the relaxation actually
    # happened - without it the barrier would engage on a pipeline that
    # declared it did not want one, and delivery would be held back for no
    # reason the caller asked for
    seen: list[int] = []

    # when
    await Stream.of(values).parallel().unordered().map(_delay_by_position).for_each_ordered(seen.append)

    # then the positional delay decided the order, not the source
    assert sorted(seen) == sorted(values)
    assert seen != values


@pytest.mark.asyncio
async def test_sorted_after_unordered_restores_the_for_each_ordered_guarantee() -> None:
    # given the positional delay queued *before* the sort, so the racing
    # branches really do split the source between them. Without it a sort that
    # had stopped restoring the characteristic would still be indistinguishable
    # here: the pipeline would run unordered under RACING with no barrier, and
    # this would only catch it if the branches had each sorted a subset
    seen: list[int] = []

    # when
    await (
        Stream.of(values)
        .parallel()
        .unordered()
        .map(_delay_by_position)
        .sorted(lambda a, b: a - b)
        .for_each_ordered(seen.append)
    )

    # then: sorted() set the ordering characteristic again, so the encounter
    # order for_each_ordered() honours is the sorted one
    assert seen == sorted(values)


# --- the ordered guarantee does not serialize the chain --------------------
#
# The guarantee used to be bought by naming SEQUENTIAL, which forfeited every
# drop of concurrency the caller asked for. It is now the racing executor's
# delivery barrier, so the chain still races and only the handing over to the
# consumer is ordered. These pin that difference: without them, a regression to
# the single-flight drive would leave the whole suite green.


@pytest.mark.asyncio
async def test_ordered_for_each_ordered_does_not_serialize_the_chain() -> None:
    # given a mapper that records when it was inside, so the claim is tested
    # directly rather than through a wall-clock threshold
    intervals: list[tuple[float, float]] = []

    async def timed(n: int) -> int:
        entered = time.perf_counter()
        await asyncio.sleep(delay_by_position[n])
        intervals.append((entered, time.perf_counter()))
        return n

    seen: list[int] = []

    # when
    await Stream.of(values).parallel().map(timed).for_each_ordered(seen.append)

    # then the consumer saw encounter order
    assert seen == values

    # and at least two mapper calls were in flight at once, which a
    # single-flight drive could never produce
    overlapping = any(
        a_start < b_end and b_start < a_end
        for i, (a_start, a_end) in enumerate(intervals)
        for b_start, b_end in intervals[i + 1 :]
    )
    assert overlapping, "the chain ran one element at a time"


@pytest.mark.asyncio
async def test_ordered_for_each_ordered_is_faster_than_sequential() -> None:
    # given the same pipeline under each mode. Loose threshold on purpose: the
    # test above is the one that pins the claim, and this one is here because
    # wall clock is what a caller actually notices
    async def run(stream: Stream[int]) -> float:
        started = time.perf_counter()
        await stream.map(_delay_by_position).for_each_ordered(lambda _: None)
        return time.perf_counter() - started

    # when
    parallel = await run(Stream.of(values).parallel())
    sequential = await run(Stream.of(values).sequential())

    # then
    assert parallel < sequential / 2


# --- the guarantee's boundary: the consumer, and nothing upstream ----------


@pytest.mark.asyncio
async def test_an_op_upstream_of_for_each_ordered_is_not_ordered() -> None:
    # given a side effect queued upstream of the terminal, and one inside it
    peeked: list[int] = []
    consumed: list[int] = []

    # when
    await Stream.of(values).parallel().peek(peeked.append).map(_delay_by_position).for_each_ordered(consumed.append)

    # then the consumer is ordered, as promised
    assert consumed == values

    # and peek() saw every element exactly once, in an order this call does not
    # constrain - Java promises encounter order for the action and says nothing
    # about upstream stages
    assert sorted(peeked) == sorted(values)


@pytest.mark.asyncio
async def test_the_same_side_effect_in_the_consumer_is_ordered() -> None:
    # given the side effect moved from peek() into the consumer - the migration
    # the README entry points a caller at
    recorded: list[int] = []

    # when
    await Stream.of(values).parallel().map(_delay_by_position).for_each_ordered(recorded.append)

    # then
    assert recorded == values
