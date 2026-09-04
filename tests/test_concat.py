import asyncio

import pytest

from snakestream.collector import to_generator
from snakestream.collectors import to_list
from snakestream.exception import IllegalStateException
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_concat_simple() -> None:
    # when
    a = Stream.of([1, 2, 3, 4])
    b = Stream.of([5, 6, 7])

    generator = Stream.concat(a, b).collect(to_generator)

    # then
    assert await generator.__anext__() == 1
    assert await generator.__anext__() == 2
    assert await generator.__anext__() == 3
    assert await generator.__anext__() == 4
    assert await generator.__anext__() == 5
    assert await generator.__anext__() == 6
    assert await generator.__anext__() == 7

    with pytest.raises(StopAsyncIteration):
        await generator.__anext__()


@pytest.mark.asyncio
async def test_concat_with_intermediaries() -> None:
    # when
    a = Stream.of([1, 2, 3, 4]).filter(lambda x: x < 3)
    b = Stream.of([5, 6, 7, 7]).distinct()

    generator = Stream.concat(a, b).collect(to_generator)

    # then
    assert await generator.__anext__() == 1
    assert await generator.__anext__() == 2
    assert await generator.__anext__() == 5
    assert await generator.__anext__() == 6
    assert await generator.__anext__() == 7

    with pytest.raises(StopAsyncIteration):
        await generator.__anext__()


@pytest.mark.asyncio
async def test_concat_returns_a_stream_without_await() -> None:
    # when
    result = Stream.concat(Stream.of([1, 2]), Stream.of([3]))

    # then
    assert isinstance(result, Stream)
    assert await result.collect(to_list()) == [1, 2, 3]


@pytest.mark.asyncio
async def test_concat_result_is_not_awaitable() -> None:
    # when
    result = Stream.concat(Stream.of([1, 2]), Stream.of([3]))

    # then
    with pytest.raises(TypeError):
        await result  # type: ignore[misc]


def test_concat_is_callable_outside_a_coroutine() -> None:
    # when
    result = Stream.concat(Stream.of([1, 2]), Stream.of([3]))

    # then
    assert isinstance(result, Stream)


@pytest.mark.asyncio
async def test_concat_with_an_empty_first_stream() -> None:
    # when
    result = Stream.concat(Stream.empty(), Stream.of([1, 2, 3]))

    # then
    assert await result.collect(to_list()) == [1, 2, 3]


@pytest.mark.asyncio
async def test_concat_with_an_empty_second_stream() -> None:
    # when
    result = Stream.concat(Stream.of([1, 2, 3]), Stream.empty())

    # then
    assert await result.collect(to_list()) == [1, 2, 3]


@pytest.mark.asyncio
async def test_concat_pulls_nothing_until_consumed() -> None:
    # given
    seen: list[int] = []

    # when
    Stream.concat(
        Stream.of([1, 2]).peek(seen.append),
        Stream.of([3, 4]).peek(seen.append),
    )

    # then
    assert seen == []


@pytest.mark.asyncio
async def test_concat_leaves_the_second_stream_untouched_until_the_first_is_done() -> None:
    # given
    from_a: list[int] = []
    from_b: list[int] = []

    generator = Stream.concat(
        Stream.of([1, 2]).peek(from_a.append),
        Stream.of([3, 4]).peek(from_b.append),
    ).collect(to_generator)

    # when
    assert await generator.__anext__() == 1
    assert await generator.__anext__() == 2

    # then
    assert from_a == [1, 2]
    assert from_b == []


def test_concat_carries_both_operands_close_handlers_in_order(mocker) -> None:
    calls = []
    a1 = mocker.Mock(side_effect=lambda: calls.append("a1"))
    a2 = mocker.Mock(side_effect=lambda: calls.append("a2"))
    b1 = mocker.Mock(side_effect=lambda: calls.append("b1"))
    b2 = mocker.Mock(side_effect=lambda: calls.append("b2"))

    a = Stream.of([1, 2]).on_close(a1).on_close(a2)
    b = Stream.of([3, 4]).on_close(b1).on_close(b2)

    # when
    Stream.concat(a, b).close()

    # then
    assert calls == ["a1", "a2", "b1", "b2"]


def test_concat_with_only_one_side_having_handlers(mocker) -> None:
    b1 = mocker.Mock()

    a = Stream.of([1, 2])
    b = Stream.of([3, 4]).on_close(b1)

    # when
    Stream.concat(a, b).close()

    # then
    b1.assert_called_once()


def test_concat_with_neither_side_having_handlers() -> None:
    a = Stream.of([1, 2])
    b = Stream.of([3, 4])

    # when / then
    Stream.concat(a, b).close()


def test_concat_does_not_pick_up_handlers_registered_after_concat(mocker) -> None:
    late_handler = mocker.Mock()

    a = Stream.of([1, 2])
    b = Stream.of([3, 4])

    concatenated = Stream.concat(a, b)
    a.on_close(late_handler)

    # when
    concatenated.close()

    # then
    late_handler.assert_not_called()


def test_concat_raising_handler_on_a_does_not_skip_bs_handler(mocker) -> None:
    bad_a = mocker.Mock(side_effect=ValueError("boom"))
    good_b = mocker.Mock()

    a = Stream.of([1, 2]).on_close(bad_a)
    b = Stream.of([3, 4]).on_close(good_b)

    # when
    with pytest.raises(ValueError, match="boom"):
        Stream.concat(a, b).close()

    # then
    bad_a.assert_called_once()
    good_b.assert_called_once()


# --- the concatenated stream carries both operands' characteristics ---------
#
# Java's Stream.concat documents one sentence this file's tests split in two:
# the result "is ordered if both of the input streams are ordered, and parallel
# if either of the input streams is parallel". Before
# concat-carries-characteristics, concat() built a base Stream with an empty
# chain and the default executor, so it carried the operands' elements and
# close handlers and nothing else they knew about themselves.


@pytest.mark.asyncio
async def test_concat_of_two_parallel_streams_is_parallel() -> None:
    assert Stream.concat(Stream.of([1, 2, 3]).parallel(), Stream.of([4, 5]).parallel()).is_parallel() is True


@pytest.mark.asyncio
async def test_concat_is_parallel_when_only_one_operand_is() -> None:
    assert Stream.concat(Stream.of([1, 2, 3]).parallel(), Stream.of([4, 5])).is_parallel() is True
    assert Stream.concat(Stream.of([1, 2, 3]), Stream.of([4, 5]).parallel()).is_parallel() is True


@pytest.mark.asyncio
async def test_concat_of_two_sequential_streams_is_sequential() -> None:
    assert Stream.concat(Stream.of([1, 2, 3]), Stream.of([4, 5])).is_parallel() is False


@pytest.mark.asyncio
async def test_a_later_mode_switch_still_governs_a_concatenation() -> None:
    # the mode concat() derives is an ordinary executor, not a special status:
    # sequential() overrides it exactly as it overrides a parallel() call
    c = Stream.concat(Stream.of([1, 2, 3]).parallel(), Stream.of([4, 5]).parallel())
    assert c.sequential().is_parallel() is False


@pytest.mark.asyncio
async def test_concat_of_two_ordered_streams_is_ordered() -> None:
    assert Stream.concat(Stream.of([1, 2, 3]), Stream.of([4, 5]))._is_ordered() is True


@pytest.mark.asyncio
async def test_concat_is_unordered_when_either_operand_is() -> None:
    assert Stream.concat(Stream.of([1, 2, 3]).unordered(), Stream.of([4, 5]))._is_ordered() is False
    assert Stream.concat(Stream.of([1, 2, 3]), Stream.of([4, 5]).unordered())._is_ordered() is False
    assert Stream.concat(Stream.of([1, 2, 3]).unordered(), Stream.of([4, 5]).unordered())._is_ordered() is False


@pytest.mark.asyncio
async def test_an_unordered_concatenation_stays_unordered_when_extended() -> None:
    # the characteristic is derived from the chain rather than stored, so ops
    # queued onto the result see it the way they see any positional answer
    c = Stream.concat(Stream.of([1, 2, 3]).unordered(), Stream.of([4, 5]))
    assert c.map(lambda x: x).filter(lambda x: True)._is_ordered() is False


@pytest.mark.asyncio
async def test_concat_invalidates_the_first_operand() -> None:
    a, b = Stream.of([1, 2, 3]), Stream.of([4, 5])
    Stream.concat(a, b)
    with pytest.raises(IllegalStateException):
        await a.collect(to_list())


@pytest.mark.asyncio
async def test_concat_invalidates_the_second_operand() -> None:
    a, b = Stream.of([1, 2, 3]), Stream.of([4, 5])
    Stream.concat(a, b)
    with pytest.raises(IllegalStateException):
        b.map(lambda x: x)


@pytest.mark.asyncio
async def test_draining_an_operand_after_concat_raises_rather_than_shortening() -> None:
    # the defect this replaces, recorded because the wrongness is the point:
    # concat() left both operands live over the source the concatenation also
    # draws from, so `await a.collect(to_list())` returned [1, 2, 3] and the
    # concatenation then yielded [4, 5] - a silently shortened result, no
    # exception anywhere. Java raises here; AbstractPipeline marks the operands
    # of concat linked, and a later operation on one throws.
    a, b = Stream.of([1, 2, 3]), Stream.of([4, 5])
    c = Stream.concat(a, b)
    with pytest.raises(IllegalStateException):
        await a.collect(to_list())
    assert await c.collect(to_list()) == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_invalidation_fires_at_call_time() -> None:
    a, b = Stream.of([1, 2, 3]), Stream.of([4, 5])
    Stream.concat(a, b)
    # nothing has been pulled from the concatenation yet
    with pytest.raises(IllegalStateException):
        a.map(lambda x: x)


@pytest.mark.asyncio
async def test_the_same_operand_cannot_be_concatenated_twice() -> None:
    a, b, c = Stream.of([1, 2, 3]), Stream.of([4, 5]), Stream.of([6])
    Stream.concat(a, b)
    with pytest.raises(IllegalStateException):
        Stream.concat(a, c)


@pytest.mark.asyncio
async def test_the_concatenated_stream_itself_is_unaffected_by_the_invalidation() -> None:
    c = Stream.concat(Stream.of([1, 2, 3]), Stream.of([4, 5]))
    assert await c.map(lambda x: x * 2).collect(to_list()) == [2, 4, 6, 8, 10]


@pytest.mark.asyncio
async def test_an_unordered_concatenation_still_partitions_in_encounter_order() -> None:
    # given the shape the racing tests use throughout: the early elements are
    # the expensive ones, so under a plain race the cheap tail overtakes the
    # slow head and arrival order and encounter order disagree visibly. Without
    # it a passing assertion would prove nothing.
    source = list(range(20))

    async def slow_head(n: int) -> int:
        await asyncio.sleep(0.05 if n < 5 else 0.001)
        return n

    # when a concatenation of unordered operands is raced into to_list(),
    # which gained a combiner (make-combiners-live, task 4.1): a partitioned
    # merge is always in batch (encounter) order regardless of unordered()
    # (parallel-reduction), so the operands' unordered() no longer buys back
    # race-order delivery here - see test_racing_delivery_order.py's own
    # pair of tests for the collector that still shows the old behaviour.
    c = Stream.concat(Stream.of(source).unordered(), Stream.of([]).unordered())
    seen = await c.parallel().map(slow_head).collect(to_list())

    assert seen == source


@pytest.mark.asyncio
async def test_an_ordered_concatenation_still_delivers_in_encounter_order() -> None:
    # the other side of the same coin, so the test above is known to be
    # measuring the characteristic rather than the racing executor's mood
    source = list(range(20))

    async def slow_head(n: int) -> int:
        await asyncio.sleep(0.05 if n < 5 else 0.001)
        return n

    c = Stream.concat(Stream.of(source), Stream.of([]))
    assert await c.parallel().map(slow_head).collect(to_list()) == source


def test_concat_of_two_instances_of_one_subclass_is_a_base_stream() -> None:
    class MyStream(Stream):
        pass

    c = Stream.concat(MyStream([1, 2]), MyStream([3]))
    assert type(c) is Stream


@pytest.mark.asyncio
async def test_concat_of_two_different_subclasses_does_not_raise() -> None:
    class OneStream(Stream):
        pass

    class OtherStream(Stream):
        pass

    c = Stream.concat(OneStream([1, 2]), OtherStream([3]))
    assert type(c) is Stream
    assert await c.collect(to_list()) == [1, 2, 3]
