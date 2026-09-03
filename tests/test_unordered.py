import asyncio

import pytest

from snakestream.collectors import to_list
from snakestream.exception import IllegalStateException
from conftest import TIE_SOURCE, TIED_EARLY, TIED_LATE, by_key, overtaken
from snakestream.comparator import comparing
from snakestream.ordering import OrderDemand, _split_point
from snakestream.ops import _MapOp
from snakestream.stream import Stream


def _asc(a: int, b: int) -> int:
    return a - b


# The ordering characteristic is not public API - Java's BaseStream exposes
# isParallel() and nothing else - so these tests assert what a pipeline *does*,
# not what an accessor returns. for_each_ordered() is the observable: it forces
# SEQUENTIAL when the pipeline is ordered and follows the stream's own executor
# when it is not.
#
# Same jumbled-source-with-positional-delay setup as
# tests/test_for_each_ordered.py and tests/test_find_first.py: a non-ascending
# source so "encounter order" is visibly distinct from "sorted by value", and
# earlier positions delayed longer than later ones so the racing branches have
# real reordering pressure on the queued .map() step.
values = [4, 1, 7, 2, 8, 3, 6, 5]
delay_by_position = {value: (len(values) - position) * 0.01 for position, value in enumerate(values)}


async def _delay_by_position(n: int) -> int:
    await asyncio.sleep(delay_by_position[n])
    return n


async def _drain_ordered(stream: Stream[int]) -> list[int]:
    """Run a pipeline under for_each_ordered() with the positional delay
    queued, and report what order the consumer saw. Equal to the pipeline's
    encounter order when the pipeline is ordered; scrambled by the race when it
    is not."""
    seen: list[int] = []
    await stream.map(_delay_by_position).for_each_ordered(seen.append)
    return seen


# --- a stream is ordered until something clears it ---------------------------


@pytest.mark.asyncio
async def test_a_new_sequential_stream_is_ordered() -> None:
    # when
    seen = await _drain_ordered(Stream.of(values))
    # then
    assert seen == values


@pytest.mark.asyncio
async def test_a_new_parallel_stream_is_ordered() -> None:
    # when: .parallel() alone does not relax encounter order, so
    # for_each_ordered() still forces a single ordered flight
    seen = await _drain_ordered(Stream.of(values).parallel())
    # then
    assert seen == values


@pytest.mark.asyncio
async def test_a_chain_of_order_preserving_ops_stays_ordered() -> None:
    # when: map/filter contribute nothing to the characteristic
    seen = await _drain_ordered(Stream.of(values).parallel().map(lambda x: x).filter(lambda x: True))
    # then
    assert seen == values


@pytest.mark.asyncio
async def test_unordered_clears_the_encounter_order_requirement() -> None:
    # when: the pipeline no longer requires encounter order, so
    # for_each_ordered() keeps the concurrency the caller asked for instead of
    # forfeiting it
    seen = await _drain_ordered(Stream.of(values).parallel().unordered())

    # then: every element exactly once, but not in encounter order - the
    # positional delay decides who finishes first
    assert sorted(seen) == sorted(values)
    assert seen != values


@pytest.mark.asyncio
async def test_unordered_does_not_affect_other_instances() -> None:
    # given
    a = Stream.of(values)
    b = Stream.of(values)

    # when
    a.unordered()

    # then: b was never touched and is still ordered
    assert await _drain_ordered(b.parallel()) == values


# --- unordered() is an ordinary intermediate op ------------------------------


@pytest.mark.asyncio
async def test_unordered_returns_a_distinct_instance() -> None:
    # given
    stream = Stream.of([1, 2, 3])

    # when
    res = stream.unordered()

    # then
    assert res is not stream


@pytest.mark.asyncio
async def test_unordered_consumes_the_receiver() -> None:
    # given
    stream = Stream.of([1, 2, 3])
    stream.unordered()

    # when / then: unordered() is an ordinary intermediate op now, so the
    # superseded reference is invalidated like any other
    with pytest.raises(IllegalStateException):
        stream.filter(lambda x: True)


@pytest.mark.asyncio
async def test_unordered_chains_with_other_intermediate_ops() -> None:
    # when
    res = await Stream.of([1, 2, 3, 4]).unordered().filter(lambda x: x % 2 == 0).collect(to_list())
    # then
    assert sorted(res) == [2, 4]


# --- positionality ----------------------------------------------------------
#
# The point of unordered() being a queued op rather than an instance flag: it
# clears encounter order from its own position downstream, and nothing else.


@pytest.mark.asyncio
async def test_unordered_leaves_earlier_ops_untouched() -> None:
    # given: an op queued before unordered() and another after it
    seen: list[int] = []

    # when
    res = await Stream.of([1, 2, 3, 4]).peek(seen.append).unordered().filter(lambda x: x % 2 == 0).collect(to_list())

    # then: the peek still saw every element, in position, and the filter
    # after the boundary still ran
    assert seen == [1, 2, 3, 4]
    assert res == [2, 4]


@pytest.mark.asyncio
async def test_unordered_position_does_not_change_the_elements_produced() -> None:
    # when
    before = await Stream.of([3, 1, 2]).unordered().map(lambda x: x * 2).collect(to_list())
    after = await Stream.of([3, 1, 2]).map(lambda x: x * 2).unordered().collect(to_list())
    without = await Stream.of([3, 1, 2]).map(lambda x: x * 2).collect(to_list())

    # then
    assert before == after == without == [6, 2, 4]


# --- sorted() restores encounter order --------------------------------------
#
# Behavioural, like everything above them. They could not be until the racing
# executor honoured encounter order: a sort was order-blind there, so a sort
# under RACING was indistinguishable from an unordered one and a behavioural
# assertion would have pinned the defect rather than the rule. What each one
# reads the characteristic through is what an order-sensitive op queued after
# the sort selects - limit(3) taking the three smallest under the comparator is
# something it can only do on a stream that arrived sorted.


@pytest.mark.asyncio
async def test_sorted_after_unordered_is_ordered_again() -> None:
    # when: a sort imposes an encounter order whether or not its input had one
    res = await Stream.of(values).parallel().unordered().map(_delay_by_position).sorted(_asc).limit(3).collect(to_list())
    # then the limit selected on the sorted encounter order
    assert res == [1, 2, 3]


@pytest.mark.asyncio
async def test_unordered_after_sorted_is_unordered() -> None:
    # given a positional delay after the sort, so the branches finish the
    # sorted stream out of order
    seen = await _drain_ordered(Stream.of(values).parallel().sorted(_asc).unordered())
    # then the pipeline took the order-blind path downstream of the
    # unordered(), keeping the concurrency rather than delivering in sorted
    # order
    assert sorted(seen) == sorted(values)
    assert seen != sorted(values)


@pytest.mark.asyncio
async def test_unordered_between_two_sorts_is_ordered() -> None:
    # when: the fold is left to right, so the last op to speak wins
    res = (
        await Stream.of(values)
        .parallel()
        .sorted(_asc)
        .unordered()
        .map(_delay_by_position)
        .sorted(_asc)
        .limit(3)
        .collect(to_list())
    )
    # then
    assert res == [1, 2, 3]


@pytest.mark.asyncio
async def test_ops_after_a_sort_preserve_the_restored_ordering() -> None:
    # when: an order-preserving op sits between the sort and the op that reads
    # the characteristic
    res = (
        await Stream.of(values)
        .parallel()
        .unordered()
        .map(_delay_by_position)
        .sorted(_asc)
        .map(lambda x: x * 10)
        .limit(3)
        .collect(to_list())
    )
    # then the restored characteristic survived the intervening map
    assert res == [10, 20, 30]


# --- mode switches ----------------------------------------------------------
#
# These four assert on the internal accessor rather than on behaviour, and are
# the only tests in the suite that do. It is deliberate: survival across a mode
# switch has no behavioural observable, because every terminal that consults
# ordering does so at the end of the pipeline, by which point a switched stream
# and a directly-constructed one with the same chain and executor are
# indistinguishable - which is exactly the property under test. The alternative
# is leaving the rule unpinned, and it is the rule whose earlier violation
# produced a wrong answer. See the make-is-ordered-internal design doc.


@pytest.mark.asyncio
async def test_unordered_survives_parallel_switch() -> None:
    # when
    res = Stream.of([1, 2, 3]).unordered().parallel()._is_ordered()
    # then
    assert res is False


@pytest.mark.asyncio
async def test_unordered_survives_sequential_switch() -> None:
    # when
    res = Stream.of([1, 2, 3]).parallel().unordered().sequential()._is_ordered()
    # then
    assert res is False


@pytest.mark.asyncio
async def test_ordered_stays_true_across_parallel_switch() -> None:
    # when
    res = Stream.of([1, 2, 3]).parallel()._is_ordered()
    # then
    assert res is True


@pytest.mark.asyncio
async def test_ordered_stays_true_across_sequential_switch() -> None:
    # when
    res = Stream.of([1, 2, 3]).parallel().sequential()._is_ordered()
    # then
    assert res is True


# --- the accessor is not public API -----------------------------------------


@pytest.mark.asyncio
async def test_the_public_ordering_accessor_does_not_exist() -> None:
    # given: Java's BaseStream exposes isParallel() and nothing else; ORDERED
    # lives in the package-private StreamOpFlag and is never readable
    stream = Stream.of([1, 2, 3])

    # then
    assert not hasattr(stream, "is_ordered")
    with pytest.raises(AttributeError):
        stream.is_ordered()  # type: ignore[attr-defined]


# --- unordered() releases min()/max() from the delivery barrier --------------
#
# comparator-contract specifies ties as *unspecified* here, matching Java, whose
# parallel min()/max() on an unordered pipeline may break ties any way. What is
# specified is that the value is still right, that no barrier is engaged, and
# that a caller who wants determinism has a lever that does not cost one: a
# total comparator via then_comparing(). See conftest for the source.


@pytest.mark.asyncio
async def test_unordered_max_returns_one_of_the_tied_records() -> None:
    # when
    it = await Stream.of(TIE_SOURCE).parallel().unordered().map(overtaken).max(by_key)
    # then - either is valid; the extreme key is not
    assert it in (TIED_EARLY, TIED_LATE)
    assert it[1] == 5


@pytest.mark.asyncio
async def test_unordered_max_engages_no_delivery_barrier() -> None:
    # given: a chain with no order-sensitive op, so the terminal's own
    # declaration is the only thing that could split it
    chain = [_MapOp(overtaken)]

    # then: max() observes order, but unordered() clears the characteristic
    assert _split_point(chain, demand=OrderDemand.IF_ORDERED, ordered_in=True) == len(chain)
    assert _split_point(chain, demand=OrderDemand.IF_ORDERED, ordered_in=False) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("run", range(3))
async def test_a_total_comparator_is_determinate_on_an_unordered_pipeline(run) -> None:
    # given: the tie broken by data rather than by position
    total = comparing(lambda pair: pair[1]).then_comparing(lambda pair: pair[0])

    # when
    it = await Stream.of(TIE_SOURCE).parallel().unordered().map(overtaken).max(total)

    # then: "late" > "early" on the tie-break segment, on every run
    assert it == TIED_LATE
