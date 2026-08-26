import asyncio

import pytest

from snakestream.collectors import to_list
from snakestream.exception import IllegalStateException
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
# This whole section asserts on the internal accessor rather than on behaviour,
# and unlike the mode-switch tests below the reason is temporary rather than
# structural: observing the rule needs a sort running under RACING, and that
# path produces a wrong answer in its own right today. _SortedOp is a
# StatelessOp, so over a list source one branch takes everything and emits it
# sorted whatever the characteristic says, while over an async source the
# branches each sort their own subset and the merged output is not sorted at
# all. A behavioural assertion would therefore pin a defect rather than the
# rule - verified, not assumed: with _SortedOp.ordering flipped to PRESERVE so
# that sorted() no longer restores ordering, behavioural forms of all four of
# these still passed. Restate them behaviourally once ordered sorted() under
# RACING lands; it is the first item in the roadmap's Now bucket.


@pytest.mark.asyncio
async def test_sorted_after_unordered_is_ordered_again() -> None:
    # when: a sort imposes an encounter order whether or not its input had one
    res = Stream.of(values).parallel().unordered().sorted(_asc)._is_ordered()
    # then
    assert res is True


@pytest.mark.asyncio
async def test_unordered_after_sorted_is_unordered() -> None:
    # when
    res = Stream.of(values).parallel().sorted(_asc).unordered()._is_ordered()
    # then
    assert res is False


@pytest.mark.asyncio
async def test_unordered_between_two_sorts_is_ordered() -> None:
    # when: the fold is left to right, so the last op to speak wins
    res = Stream.of(values).parallel().sorted(_asc).unordered().sorted(_asc)._is_ordered()
    # then
    assert res is True


@pytest.mark.asyncio
async def test_ops_after_a_sort_preserve_the_restored_ordering() -> None:
    # when
    res = Stream.of(values).parallel().unordered().sorted(_asc).map(lambda x: x)._is_ordered()
    # then
    assert res is True


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
