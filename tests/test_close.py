from contextlib import closing

import pytest

from snakestream.collectors import to_list
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_close_simple(mocker, int_2_letter) -> None:
    mock_callback1 = mocker.Mock()
    mock_callback2 = mocker.Mock()

    stream = Stream.of([1, 2, 3, 4, 1, 2, 3, 4])

    it = (
        await stream.map(lambda x: int_2_letter[x])
        .distinct()
        .on_close(mock_callback1)
        .on_close(mock_callback2)
        .collect(to_list())
    )

    # when
    stream.close()

    # then
    mock_callback1.assert_called_once()
    mock_callback2.assert_called_once()

    assert len(it) == 4
    assert "a" in it
    assert "b" in it
    assert "c" in it
    assert "d" in it


@pytest.mark.asyncio
async def test_close_after_stream_switch(mocker, int_2_letter) -> None:
    mock_callback1 = mocker.Mock()
    mock_callback2 = mocker.Mock()

    stream = Stream.of([1, 2, 3, 4, 1, 2, 3, 4])

    await (
        stream.map(lambda x: int_2_letter[x])
        .on_close(mock_callback1)
        .distinct()
        .parallel()
        .on_close(mock_callback2)
        .collect(to_list())
    )

    # when
    stream.close()

    # then
    mock_callback1.assert_called_once()
    mock_callback2.assert_called_once()


@pytest.mark.asyncio
async def test_close_after_sequential_switch(mocker, int_2_letter) -> None:
    mock_callback1 = mocker.Mock()
    mock_callback2 = mocker.Mock()

    stream = Stream.of([1, 2, 3, 4, 1, 2, 3, 4])

    await (
        stream.map(lambda x: int_2_letter[x])
        .on_close(mock_callback1)
        .parallel()
        .distinct()
        .sequential()
        .on_close(mock_callback2)
        .collect(to_list())
    )

    # when
    stream.close()

    # then
    mock_callback1.assert_called_once()
    mock_callback2.assert_called_once()


def test_close_invokes_handlers_in_registration_order(mocker) -> None:
    calls = []
    mock_callback1 = mocker.Mock(side_effect=lambda: calls.append("first"))
    mock_callback2 = mocker.Mock(side_effect=lambda: calls.append("second"))

    stream = Stream.of([1, 2, 3])
    stream.on_close(mock_callback1).on_close(mock_callback2)

    # when
    stream.close()

    # then
    assert calls == ["first", "second"]


def test_close_with_no_handlers_is_a_noop() -> None:
    stream = Stream.of([1, 2, 3])

    # when / then
    stream.close()


@pytest.mark.asyncio
async def test_construct_with_initial_close_handlers(mocker, int_2_letter) -> None:
    mock_callback = mocker.Mock()

    stream = Stream([1, 2, 3], [mock_callback])
    await stream.collect(to_list())

    # when
    stream.close()

    # then
    mock_callback.assert_called_once()


def test_close_runs_remaining_handlers_after_one_raises(mocker) -> None:
    bad = mocker.Mock(side_effect=ValueError("boom"))
    good = mocker.Mock()

    stream = Stream.of([1, 2, 3])
    stream.on_close(bad).on_close(good)

    # when
    with pytest.raises(ValueError, match="boom"):
        stream.close()

    # then
    bad.assert_called_once()
    good.assert_called_once()


def test_close_with_multiple_raising_handlers_runs_all_and_raises_first(mocker) -> None:
    bad_a = mocker.Mock(side_effect=ValueError("first"))
    bad_b = mocker.Mock(side_effect=ValueError("second"))

    stream = Stream.of([1, 2, 3])
    stream.on_close(bad_a).on_close(bad_b)

    # when
    with pytest.raises(ValueError, match="first"):
        stream.close()

    # then
    bad_a.assert_called_once()
    bad_b.assert_called_once()


def test_close_with_three_raising_handlers_notes_the_other_two(mocker) -> None:
    bad_a = mocker.Mock(side_effect=ValueError("first"))
    bad_b = mocker.Mock(side_effect=ValueError("second"))
    bad_c = mocker.Mock(side_effect=ValueError("third"))

    stream = Stream.of([1, 2, 3])
    stream.on_close(bad_a).on_close(bad_b).on_close(bad_c)

    # when
    with pytest.raises(ValueError, match="first") as exc_info:
        stream.close()

    # then
    bad_a.assert_called_once()
    bad_b.assert_called_once()
    bad_c.assert_called_once()
    assert len(exc_info.value.__notes__) == 2
    assert "second" in exc_info.value.__notes__[0]
    assert "third" in exc_info.value.__notes__[1]


def test_close_with_a_single_raising_handler_gains_no_notes(mocker) -> None:
    bad = mocker.Mock(side_effect=ValueError("boom"))

    stream = Stream.of([1, 2, 3])
    stream.on_close(bad)

    # when
    with pytest.raises(ValueError, match="boom") as exc_info:
        stream.close()

    # then
    bad.assert_called_once()
    assert not getattr(exc_info.value, "__notes__", [])


@pytest.mark.asyncio
async def test_autoclose_simple(mocker, monkeypatch, int_2_letter):
    # given
    stream = Stream.of([1, 2, 3, 4, 1, 2, 3, 4])
    close_mock = mocker.Mock()
    monkeypatch.setattr(stream, "close", close_mock)

    # when
    with closing(stream) as stream:
        it = await stream.map(lambda x: int_2_letter[x]).distinct().collect(to_list())

    # then
    close_mock.assert_called_once()
    assert len(it) == 4
