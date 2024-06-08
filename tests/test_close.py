
from contextlib import closing
import pytest

from snakestream.collector import to_list
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_close_simple(mocker, int_2_letter) -> None:
    mock_callback1 = mocker.Mock()
    mock_callback2 = mocker.Mock()

    stream = Stream.of([1, 2, 3, 4, 1, 2, 3, 4])

    it = await stream \
        .map(lambda x: int_2_letter[x]) \
        .distinct() \
        .on_close(mock_callback1) \
        .on_close(mock_callback2) \
        .collect(to_list)

    # when
    stream.close()

    # then
    mock_callback1.assert_called_once()
    mock_callback2.assert_called_once()

    assert 4 == len(it)
    assert 'a' in it
    assert 'b' in it
    assert 'c' in it
    assert 'd' in it


@pytest.mark.asyncio
async def test_close_after_stream_switch(mocker, int_2_letter) -> None:
    mock_callback1 = mocker.Mock()
    mock_callback2 = mocker.Mock()

    stream = Stream.of([1, 2, 3, 4, 1, 2, 3, 4])

    await stream \
        .map(lambda x: int_2_letter[x]) \
        .on_close(mock_callback1) \
        .distinct() \
        .parallel() \
        .on_close(mock_callback2) \
        .collect(to_list)

    # when
    stream.close()

    # then
    mock_callback1.assert_called_once()
    mock_callback2.assert_called_once()


@pytest.mark.asyncio
async def test_autoclose_simple(mocker, monkeypatch, int_2_letter):
    # given
    stream = Stream.of([1, 2, 3, 4, 1, 2, 3, 4])
    close_mock = mocker.Mock()
    monkeypatch.setattr(stream, 'close', close_mock)

    # when
    with closing(stream) as stream:
        it = await stream \
            .map(lambda x: int_2_letter[x]) \
            .distinct() \
            .collect(to_list)

    # then
    close_mock.assert_called_once()
    assert 4 == len(it)
