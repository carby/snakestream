from contextlib import closing
import pytest

from snakestream.collector import to_list
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
        .collect(to_list)
    )

    # when
    stream.close()

    # then
    mock_callback1.assert_called_once()
    mock_callback2.assert_called_once()

    assert 4 == len(it)
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
        .collect(to_list)
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
        .collect(to_list)
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
    await stream.collect(to_list)

    # when
    stream.close()

    # then
    mock_callback.assert_called_once()


@pytest.mark.asyncio
async def test_autoclose_simple(mocker, monkeypatch, int_2_letter):
    # given
    stream = Stream.of([1, 2, 3, 4, 1, 2, 3, 4])
    close_mock = mocker.Mock()
    monkeypatch.setattr(stream, "close", close_mock)

    # when
    with closing(stream) as stream:
        it = await stream.map(lambda x: int_2_letter[x]).distinct().collect(to_list)

    # then
    close_mock.assert_called_once()
    assert 4 == len(it)
