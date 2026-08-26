import pytest

from snakestream.collectors import to_list
from snakestream.exception import IllegalStateException
from snakestream.stream import Stream


def _asc(a: int, b: int) -> int:
    return a - b


@pytest.mark.asyncio
async def test_is_ordered_default_sequential() -> None:
    # when
    res = Stream.of([1, 2, 3]).is_ordered()
    # then
    assert res is True


@pytest.mark.asyncio
async def test_is_ordered_default_parallel() -> None:
    # when
    res = Stream.of([1, 2, 3]).parallel().is_ordered()
    # then
    assert res is True


@pytest.mark.asyncio
async def test_unordered_sets_is_ordered_false() -> None:
    # when
    res = Stream.of([1, 2, 3]).unordered().is_ordered()
    # then
    assert res is False


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


@pytest.mark.asyncio
async def test_unordered_does_not_affect_other_instances() -> None:
    # given
    a = Stream.of([1, 2, 3])
    b = Stream.of([1, 2, 3])

    # when
    a2 = a.unordered()

    # then
    assert a2.is_ordered() is False
    assert b.is_ordered() is True


@pytest.mark.asyncio
async def test_unordered_survives_parallel_switch() -> None:
    # when
    res = Stream.of([1, 2, 3]).unordered().parallel().is_ordered()
    # then
    assert res is False


@pytest.mark.asyncio
async def test_unordered_survives_sequential_switch() -> None:
    # when
    res = Stream.of([1, 2, 3]).parallel().unordered().sequential().is_ordered()
    # then
    assert res is False


@pytest.mark.asyncio
async def test_ordered_stays_true_across_parallel_switch() -> None:
    # when
    res = Stream.of([1, 2, 3]).parallel().is_ordered()
    # then
    assert res is True


@pytest.mark.asyncio
async def test_ordered_stays_true_across_sequential_switch() -> None:
    # when
    res = Stream.of([1, 2, 3]).parallel().sequential().is_ordered()
    # then
    assert res is True


# --- positionality ----------------------------------------------------------
#
# The point of unordered() being a queued op rather than an instance flag: it
# clears encounter order from its own position downstream, and nothing else.


@pytest.mark.asyncio
async def test_is_ordered_true_for_a_chain_of_order_preserving_ops() -> None:
    # when
    res = Stream.of([1, 2, 3]).map(lambda x: x).filter(lambda x: True).is_ordered()
    # then
    assert res is True


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


@pytest.mark.asyncio
async def test_sorted_after_unordered_is_ordered_again() -> None:
    # when: a sort imposes an encounter order whether or not its input had one
    res = Stream.of([3, 1, 2]).unordered().sorted(_asc).is_ordered()
    # then
    assert res is True


@pytest.mark.asyncio
async def test_unordered_after_sorted_is_unordered() -> None:
    # when
    res = Stream.of([3, 1, 2]).sorted(_asc).unordered().is_ordered()
    # then
    assert res is False


@pytest.mark.asyncio
async def test_unordered_between_two_sorts_is_ordered() -> None:
    # when: the fold is left to right, so the last op to speak wins
    res = Stream.of([3, 1, 2]).sorted(_asc).unordered().sorted(_asc).is_ordered()
    # then
    assert res is True


@pytest.mark.asyncio
async def test_ops_after_a_sort_preserve_the_restored_ordering() -> None:
    # when
    res = Stream.of([3, 1, 2]).unordered().sorted(_asc).map(lambda x: x).is_ordered()
    # then
    assert res is True
