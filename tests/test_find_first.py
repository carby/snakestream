import asyncio
import time

import pytest
from collections.abc import AsyncGenerator

from snakestream import Stream
from snakestream.execution import PROCESSES, _in_flight


async def _slower_for_earlier(x: int) -> int:
    # earlier elements finish later, so arrival order != encounter order
    await asyncio.sleep((10 - x) * 0.005)
    return x


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
    async def descending() -> AsyncGenerator[int]:
        for i in range(200, 0, -1):
            await asyncio.sleep(0)
            yield i

    # when: run repeatedly - the wrong answer was nondeterministic
    results = [await Stream.of(descending()).parallel().unordered().sorted(lambda a, b: a - b).find_first() for _ in range(10)]

    # then
    assert results == [1] * 10


# --- find_first() no longer forfeits the caller's execution mode -----------
#
# It used to name SEQUENTIAL, which discarded .parallel() outright while
# is_parallel() still reported True. The demand is now expressed as
# OrderDemand.ALWAYS and the chain races under whatever mode was declared.

_SOURCE = list(range(60))
_MATCH_AT = 12


@pytest.mark.asyncio
async def test_a_dropping_chain_is_faster_in_parallel() -> None:
    # given a head that must process several elements before any answer exists
    async def slow_predicate(x: int) -> bool:
        await asyncio.sleep(0.01)
        return x >= _MATCH_AT

    async def run(stream: Stream[int]) -> tuple[int | None, float]:
        started = time.perf_counter()
        found = await stream.filter(slow_predicate).find_first()
        return found, time.perf_counter() - started

    # when
    par, par_t = await run(Stream.of(_SOURCE).parallel())
    seq, seq_t = await run(Stream.of(_SOURCE).sequential())

    # then the same element, sooner - the predicate runs across all branches
    assert par == seq == _MATCH_AT
    assert par_t < seq_t / 2


@pytest.mark.asyncio
async def test_a_non_dropping_chain_is_no_slower_in_parallel() -> None:
    # given a head that cannot drop, where racing buys nothing. It must not
    # cost anything either: the speculative maps run concurrently with the one
    # that matters rather than in front of it
    async def slow(x: int) -> int:
        await asyncio.sleep(0.02)
        return x

    async def run(stream: Stream[int]) -> tuple[int | None, float]:
        started = time.perf_counter()
        found = await stream.map(slow).find_first()
        return found, time.perf_counter() - started

    # when
    par, par_t = await run(Stream.of(_SOURCE).parallel())
    seq, seq_t = await run(Stream.of(_SOURCE).sequential())

    # then
    assert par == seq == 0
    assert par_t < seq_t * 3


@pytest.mark.asyncio
async def test_always_survives_a_split() -> None:
    # given a barrier op, then an unordered() inside the resumed tail. An
    # IF_ORDERED demand would be released by that unordered(); ALWAYS is not,
    # so the resumed race splits again at delivery
    it = await (
        Stream.of([5, 3, 8, 1, 9, 2]).parallel().sorted(lambda a, b: a - b).unordered().map(_slower_for_earlier).find_first()
    )

    # then the leftmost element of the sorted order, not of the arrival order
    assert it == 1


@pytest.mark.asyncio
async def test_find_first_no_longer_overrides_unordered_for_a_positional_op() -> None:
    # given an order-sensitive op on a pipeline the caller declared unordered.
    # limit() there already answers arbitrarily under every other terminal;
    # find_first() used to suppress that for the whole pipeline by going
    # sequential, and no longer does
    it = await Stream.of(_SOURCE).parallel().unordered().limit(8).find_first()

    # then find_first() still returns the leftmost element *of what limit
    # produced* - which is all the specs promise once the subset is arbitrary
    assert it in _SOURCE


# --- the bounded speculative work that buys the concurrency ----------------


@pytest.mark.asyncio
async def test_a_parallel_find_first_may_process_more_than_one_element() -> None:
    # given a head element slower than the ones behind it, so the branches keep
    # pulling while index 0 is outstanding - the shape that fills the window
    calls: list[int] = []

    async def timed(x: int) -> int:
        calls.append(x)
        await asyncio.sleep(0.05 if x == 0 else 0.001)
        return x

    # when
    it = await Stream.of(_SOURCE).parallel().map(timed).find_first()

    # then the right answer, and more than one element processed to get it -
    # bounded by the in-flight window. Asserted as invariants, never as the
    # measured figure: the count sits between PROCESSES and _in_flight(PROCESSES)
    # depending on how the branches interleave, which a loaded machine moves
    assert it == 0
    assert 1 < len(calls) <= _in_flight(PROCESSES)


@pytest.mark.asyncio
async def test_a_sequential_find_first_processes_exactly_one() -> None:
    # given the same chain under the mode a caller declares when a side effect
    # must happen once - the escape hatch the migration entry names
    calls: list[int] = []

    async def timed(x: int) -> int:
        calls.append(x)
        await asyncio.sleep(0.001)
        return x

    # when
    it = await Stream.of(_SOURCE).sequential().map(timed).find_first()

    # then exactly one, which is where `== 1` is safe to assert
    assert it == 0
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_a_parallel_find_first_terminates_and_leaves_no_pending_tasks() -> None:
    # given an effectively unbounded source. No short-circuiting terminal had
    # ever driven _release_in_order()'s cancellation path before this change -
    # find_first() was sequential and find_any() never splits - so this pins
    # that the branches are cancelled and the shared source closed
    async def forever() -> AsyncGenerator[int]:
        i = 0
        while True:
            await asyncio.sleep(0.001)
            yield i
            i += 1

    before = len(asyncio.all_tasks())

    # when
    it = await Stream.of(forever()).parallel().map(lambda x: x).find_first()

    # then it returned rather than hanging, and nothing was left running
    assert it == 0
    await asyncio.sleep(0.05)
    assert len(asyncio.all_tasks()) <= before
