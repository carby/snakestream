"""What a racing pipeline delivers, and in what order.

The barrier the racing executor already had served an *operation* that reads
position. This file is the second caller: the terminal. An ordered racing
pipeline delivers in encounter order to a terminal that can tell the
difference, pays nothing to one that cannot, and pays nothing at all once the
caller has said `unordered()`.

The setup throughout is a source whose *early* elements are the expensive ones,
as in tests/test_racing_encounter_order.py: under a plain race the cheap tail
overtakes the slow head, so arrival order and encounter order disagree
visibly. Without that shape a passing assertion would prove nothing.
"""

import asyncio

import pytest

from snakestream import Stream
from snakestream.collector import Characteristics, Collector, to_generator
from snakestream.collectors import to_list, to_set
from snakestream.execution import _READ_AHEAD


def _asc(a: int, b: int) -> int:
    return a - b


SOURCE = list(range(20))
SLOW_HEAD = 5


async def _slow_head(n: int) -> int:
    await asyncio.sleep(0.05 if n < SLOW_HEAD else 0.001)
    return n


async def _agen(values):
    for v in values:
        yield v


# --- delivery to an order-observing terminal --------------------------------


@pytest.mark.asyncio
async def test_an_ordered_racing_map_delivers_in_encounter_order() -> None:
    # when a chain no operation in it needs order for is collected
    res = await Stream.of(SOURCE).parallel().map(_slow_head).collect(to_list())
    # then the list is the source order, not the order the branches finished in
    assert res == SOURCE


@pytest.mark.asyncio
async def test_an_ordered_racing_pipeline_matches_the_sequential_result() -> None:
    # given a chain with a filter and a flat_map, so the head emits neither one
    # output per input nor any output for some inputs
    def _pipeline(stream: Stream[int]) -> Stream[int]:
        return stream.map(_slow_head).filter(lambda n: n % 3 != 0).flat_map(lambda n: Stream.of([n, -n]))

    # when
    parallel = await _pipeline(Stream.of(SOURCE).parallel()).collect(to_list())
    sequential = await _pipeline(Stream.of(SOURCE)).collect(to_list())

    # then
    assert parallel == sequential


@pytest.mark.asyncio
async def test_an_async_source_delivers_in_encounter_order_too() -> None:
    # given the source shape every branch really does take a share of
    res = await Stream.of(_agen(SOURCE)).parallel().map(_slow_head).collect(to_list())
    # then
    assert res == SOURCE


@pytest.mark.asyncio
async def test_reduce_folds_in_encounter_order() -> None:
    # given an accumulator that is not commutative, so the fold order shows
    res = await Stream.of(list("abcdefgh")).parallel().map(lambda c: c.upper()).reduce("", lambda a, b: a + b)
    # then
    assert res == "ABCDEFGH"


@pytest.mark.asyncio
async def test_to_array_delivers_in_encounter_order() -> None:
    # then it collects through to_list(), which declares nothing, so it observes
    assert await Stream.of(SOURCE).parallel().map(_slow_head).to_array() == SOURCE


@pytest.mark.asyncio
async def test_the_three_argument_collect_delivers_in_encounter_order() -> None:
    # given an arbitrary container and accumulator, which nothing declares
    # order-independent
    res = await Stream.of(SOURCE).parallel().map(_slow_head).collect(list, list.append, list.extend)
    # then
    assert res == SOURCE


@pytest.mark.asyncio
async def test_iterator_yields_in_encounter_order() -> None:
    # given the escape hatch, which hands raw elements to the caller
    agen = Stream.of(SOURCE).parallel().map(_slow_head).iterator()
    # then the order it yields in is observable, so it is owed
    assert [x async for x in agen] == SOURCE


@pytest.mark.asyncio
async def test_to_generator_yields_in_encounter_order() -> None:
    # given the streaming collector, which composes through iterator()
    agen = Stream.of(SOURCE).parallel().map(_slow_head).collect(to_generator)
    # then
    assert [x async for x in agen] == SOURCE


# --- terminals that observe nothing -----------------------------------------


@pytest.mark.asyncio
async def test_for_each_does_not_wait_for_encounter_order() -> None:
    # given the explicitly order-blind consumer, as Java's forEach() is
    seen: list[int] = []
    await Stream.of(SOURCE).parallel().map(_slow_head).for_each(seen.append)
    # then it saw everything, in whatever order the race resolved it
    assert sorted(seen) == SOURCE
    assert seen != SOURCE


@pytest.mark.asyncio
async def test_count_is_unaffected() -> None:
    assert await Stream.of(SOURCE).parallel().map(_slow_head).count() == len(SOURCE)


@pytest.mark.asyncio
async def test_an_order_blind_terminal_holds_nothing_back() -> None:
    # given a slow first element and an unbounded source, so a barrier would
    # stall the whole pipeline behind element 0
    async def endless():
        i = 0
        while True:
            yield i
            i += 1

    async def one_slow_element(n: int) -> int:
        await asyncio.sleep(5 if n == 0 else 0.0)
        return n

    # when an order-blind short-circuiting terminal is asked
    res = await asyncio.wait_for(
        Stream.of(endless()).parallel().map(one_slow_element).any_match(lambda n: n == 3),
        timeout=2,
    )

    # then it answered without waiting on element 0, which is what declaring
    # order-blindness buys
    assert res is True


@pytest.mark.asyncio
async def test_find_any_still_races() -> None:
    res = await Stream.of(SOURCE).parallel().map(_slow_head).find_any()
    assert res in SOURCE


@pytest.mark.asyncio
async def test_min_and_max_are_unaffected() -> None:
    assert await Stream.of(SOURCE).parallel().map(_slow_head).max(_asc) == 19
    assert await Stream.of(SOURCE).parallel().map(_slow_head).min(_asc) == 0


# --- the collector answers for itself ---------------------------------------


@pytest.mark.asyncio
async def test_to_set_takes_the_order_blind_path() -> None:
    # given the one shipped collector declaring UNORDERED
    assert Characteristics.UNORDERED in to_set().characteristics
    # when
    res = await Stream.of(SOURCE).parallel().map(_slow_head).collect(to_set())
    # then the result is right and no order was owed to get it
    assert res == set(SOURCE)


@pytest.mark.asyncio
async def test_two_collectors_differing_only_in_unordered_deliver_differently() -> None:
    # given one collector that declares it and one that does not, accumulating
    # identically so the delivery order is the only difference
    observing = Collector(list, list.append)
    blind = Collector(list, list.append, characteristics=(Characteristics.UNORDERED,))

    # when
    ordered = await Stream.of(SOURCE).parallel().map(_slow_head).collect(observing)
    scrambled = await Stream.of(SOURCE).parallel().map(_slow_head).collect(blind)

    # then the declaration is the whole of the difference
    assert ordered == SOURCE
    assert sorted(scrambled) == SOURCE
    assert scrambled != SOURCE


@pytest.mark.asyncio
async def test_a_declaring_collector_is_unaffected_under_sequential() -> None:
    # given the same two collectors on a stream with no race to opt out of
    blind = Collector(list, list.append, characteristics=(Characteristics.UNORDERED,))
    # then the declaration changes nothing at all
    assert await Stream.of(SOURCE).collect(blind) == SOURCE


# --- unordered() is the opt-out ---------------------------------------------


@pytest.mark.asyncio
async def test_unordered_removes_the_delivery_barrier() -> None:
    # when the caller declares the pipeline unordered
    res = await Stream.of(SOURCE).parallel().unordered().map(_slow_head).collect(to_list())
    # then the elements are all there and the order is the race's
    assert sorted(res) == SOURCE
    assert res != SOURCE


@pytest.mark.asyncio
async def test_unordered_is_faster_than_the_ordered_form() -> None:
    # given a slow head element, which is what head-of-line blocking costs on
    loop = asyncio.get_running_loop()

    async def one_slow_element(n: int) -> int:
        await asyncio.sleep(0.3 if n == 0 else 0.0)
        return n

    # when the ordered form is asked for its first element
    ordered = Stream.of(list(range(40))).parallel().map(one_slow_element).iterator()
    start = loop.time()
    first_ordered = await anext(ordered)
    ordered_wait = loop.time() - start
    await ordered.aclose()

    # and the unordered form is asked for its first
    unordered = Stream.of(list(range(40))).parallel().unordered().map(one_slow_element).iterator()
    start = loop.time()
    first_unordered = await anext(unordered)
    unordered_wait = loop.time() - start
    await unordered.aclose()

    # then unordered() is a performance lever on a chain with no order-sensitive
    # operation in it at all, which is what this change makes it
    assert first_ordered == 0
    assert first_unordered != 0
    assert unordered_wait < 0.1 <= ordered_wait


# --- ordering the delivery does not serialize the chain ---------------------


@pytest.mark.asyncio
async def test_ordered_delivery_still_runs_the_chain_concurrently() -> None:
    # given per-element work that only concurrency can absorb
    loop = asyncio.get_running_loop()
    values = list(range(16))

    async def sleeper(n: int) -> int:
        await asyncio.sleep(0.05)
        return n

    # when the ordered racing form is drained
    start = loop.time()
    res = await Stream.of(values).parallel().map(sleeper).collect(to_list())
    parallel_time = loop.time() - start

    # then the answer is in encounter order and it did not cost a sequential
    # pass: 16 elements at 50ms is 0.8s in one worker and about a quarter of
    # that across four
    assert res == values
    assert parallel_time < 0.5


# --- the resumed tail races -------------------------------------------------


@pytest.mark.asyncio
async def test_the_suffix_of_a_short_circuiting_pipeline_races() -> None:
    # given a limit whose downstream work is the expensive part - the shape the
    # old resume rule ran one element at a time
    loop = asyncio.get_running_loop()

    async def sleeper(n: int) -> int:
        await asyncio.sleep(0.05)
        return n

    # when
    start = loop.time()
    res = await Stream.of(list(range(40))).parallel().limit(8).map(sleeper).collect(to_list())
    elapsed = loop.time() - start

    # then the eight are the first eight in encounter order, and the map that
    # produced them ran across branches rather than one at a time (8 * 50ms)
    assert res == [0, 1, 2, 3, 4, 5, 6, 7]
    assert elapsed < 0.3


@pytest.mark.asyncio
async def test_a_raced_suffix_still_delivers_in_encounter_order() -> None:
    # given a sort, whose output order is the encounter order the map inherits
    res = await Stream.of([5, 3, 1, 4, 2]).parallel().sorted(_asc).map(_slow_head).collect(to_list())
    # then the map raced and the delivery was put back
    assert res == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_a_tail_that_sorts_again_splits_again() -> None:
    # given a barrier, a raced suffix, and a second barrier inside it
    res = await Stream.of(list(range(20, 0, -1))).parallel().limit(10).map(_slow_head).sorted(_asc).collect(to_list())
    # then the limit took the first ten in encounter order and the sort saw all
    # ten rather than each branch's share
    assert res == [11, 12, 13, 14, 15, 16, 17, 18, 19, 20]


@pytest.mark.asyncio
async def test_unordered_in_the_tail_removes_the_delivery_barrier() -> None:
    # when the caller clears the characteristic after the barrier
    res = await Stream.of(list(range(12, 0, -1))).parallel().sorted(_asc).unordered().map(_slow_head).collect(to_list())
    # then the sort still saw the whole stream, and delivery is the race's
    assert sorted(res) == list(range(1, 13))
    assert res != list(range(1, 13))


# --- what a delivery barrier does not change --------------------------------


@pytest.mark.asyncio
async def test_is_parallel_still_reports_the_executor_under_a_delivery_barrier() -> None:
    stream = Stream.of(SOURCE).parallel().map(lambda x: x)
    assert stream.is_parallel() is True
    await stream.collect(to_list())


class _CountingSource:
    """A shared source that records how often it is closed."""

    def __init__(self, n: int) -> None:
        self._it = iter(range(n))
        self.closes = 0

    def __aiter__(self) -> "_CountingSource":
        return self

    async def __anext__(self) -> int:
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration from None

    async def aclose(self) -> None:
        self.closes += 1


@pytest.mark.asyncio
async def test_a_delivery_barrier_does_not_change_how_the_source_is_closed() -> None:
    # given the same chain delivered to an order-observing and an order-blind
    # terminal, so the barrier is the only difference
    observing = _CountingSource(50)
    blind = _CountingSource(50)

    # when
    await Stream.of(observing).parallel().map(lambda x: x).collect(to_list())
    await Stream.of(blind).parallel().map(lambda x: x).count()

    # then
    assert observing.closes == blind.closes


@pytest.mark.asyncio
async def test_a_generator_source_under_a_delivery_barrier_runs_its_finally_once() -> None:
    closed: list[bool] = []

    async def source():
        try:
            for i in range(50):
                yield i
        finally:
            closed.append(True)

    # when
    res = await Stream.of(source()).parallel().map(lambda x: x).collect(to_list())

    # then
    assert res == list(range(50))
    assert closed == [True]


@pytest.mark.asyncio
async def test_an_error_under_a_delivery_barrier_propagates_without_hanging() -> None:
    # given a mapper that raises on one element, which the reorder buffer must
    # not swallow while holding elements back for it
    def _boom(n: int) -> int:
        if n == 3:
            raise ValueError("boom")
        return n

    # when / then
    with pytest.raises(ValueError, match="boom"):
        await asyncio.wait_for(
            Stream.of(SOURCE).parallel().map(_boom).collect(to_list()),
            timeout=5,
        )


@pytest.mark.asyncio
async def test_read_ahead_under_a_delivery_barrier_is_bounded() -> None:
    # given a source far longer than the window and a slow first element
    pulled: list[int] = []

    async def counting():
        for i in range(400):
            pulled.append(i)
            yield i

    async def one_slow_element(n: int) -> int:
        await asyncio.sleep(0.2 if n == 0 else 0.0)
        return n

    # when the first element is taken from a chain with no order-sensitive
    # operation in it
    agen = Stream.of(counting()).parallel().map(one_slow_element).iterator()
    first = await anext(agen)
    pulled_before_first_release = len(pulled)
    await agen.aclose()

    # then the delivery barrier is bounded exactly as an operation's is
    assert first == 0
    assert pulled_before_first_release <= _READ_AHEAD
