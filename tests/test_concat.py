import pytest

from snakestream.collector import to_generator
from snakestream.collectors import to_list
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
