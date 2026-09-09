from contextlib import closing

import pytest

from snakestream.collectors import to_list
from snakestream.exception import IllegalStateException, StreamBuildException
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_close_simple(mocker, int_2_letter) -> None:
    mock_callback1 = mocker.Mock()
    mock_callback2 = mocker.Mock()

    stream = Stream([1, 2, 3, 4, 1, 2, 3, 4])

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

    stream = Stream([1, 2, 3, 4, 1, 2, 3, 4])

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

    stream = Stream([1, 2, 3, 4, 1, 2, 3, 4])

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

    stream = Stream([1, 2, 3])
    stream.on_close(mock_callback1).on_close(mock_callback2)

    # when
    stream.close()

    # then
    assert calls == ["first", "second"]


def test_on_close_registers_an_async_handler_like_a_sync_one() -> None:
    async def async_handler() -> None:
        pass

    stream = Stream([1, 2, 3])

    result = stream.on_close(async_handler)

    assert result is stream
    assert stream._close_handlers == [async_handler]


def test_close_with_no_handlers_is_a_noop() -> None:
    stream = Stream([1, 2, 3])

    # when / then
    stream.close()


def test_a_handler_argument_is_rejected() -> None:
    # when / then: the constructor takes a source and nothing else
    with pytest.raises(TypeError):
        Stream([1, 2, 3], [lambda: None])


def test_close_runs_remaining_handlers_after_one_raises(mocker) -> None:
    bad = mocker.Mock(side_effect=ValueError("boom"))
    good = mocker.Mock()

    stream = Stream([1, 2, 3])
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

    stream = Stream([1, 2, 3])
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

    stream = Stream([1, 2, 3])
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

    stream = Stream([1, 2, 3])
    stream.on_close(bad)

    # when
    with pytest.raises(ValueError, match="boom") as exc_info:
        stream.close()

    # then
    bad.assert_called_once()
    assert not getattr(exc_info.value, "__notes__", [])


def test_close_refuses_an_async_handler() -> None:
    async def async_handler() -> None:
        pass

    stream = Stream([1, 2, 3])
    stream.on_close(async_handler)

    with pytest.raises(StreamBuildException, match="async_handler"):
        stream.close()


def test_close_refusal_does_not_stop_the_sync_handlers_around_it(mocker) -> None:
    sync_a = mocker.Mock()
    sync_c = mocker.Mock()

    async def async_b() -> None:
        pass

    stream = Stream([1, 2, 3])
    stream.on_close(sync_a).on_close(async_b).on_close(sync_c)

    with pytest.raises(StreamBuildException, match="async_b"):
        stream.close()

    sync_a.assert_called_once()
    sync_c.assert_called_once()


def test_close_refusal_takes_its_place_in_encounter_order(mocker) -> None:
    bad = mocker.Mock(side_effect=ValueError("boom"))

    async def async_b() -> None:
        pass

    stream = Stream([1, 2, 3])
    stream.on_close(bad).on_close(async_b)

    with pytest.raises(ValueError, match="boom") as exc_info:
        stream.close()

    assert len(exc_info.value.__notes__) == 1
    assert "async_b" in exc_info.value.__notes__[0]


def test_close_refuses_a_sync_def_returning_a_coroutine_after_calling_it() -> None:
    called = []

    async def _coro() -> None:
        pass

    def plain_def_returning_coroutine():
        called.append(True)
        return _coro()

    stream = Stream([1, 2, 3])
    stream.on_close(plain_def_returning_coroutine)

    with pytest.raises(StreamBuildException, match="plain_def_returning_coroutine"):
        stream.close()

    assert called == [True]


def test_close_refusal_does_not_depend_on_a_running_event_loop() -> None:
    async def async_handler() -> None:
        pass

    def close_outside_loop() -> None:
        stream = Stream([1, 2, 3])
        stream.on_close(async_handler)
        with pytest.raises(StreamBuildException, match="async_handler"):
            stream.close()

    close_outside_loop()


@pytest.mark.asyncio
async def test_close_refusal_from_inside_a_running_event_loop() -> None:
    async def async_handler() -> None:
        pass

    stream = Stream([1, 2, 3])
    stream.on_close(async_handler)

    with pytest.raises(StreamBuildException, match="async_handler"):
        stream.close()


def test_stream_over_an_already_consumed_stream_raises_at_construction() -> None:
    # _accept() unwraps a Stream source via iterator(), which calls
    # _check_not_consumed() - so this raises earlier than it used to (at
    # consumption), and at the offending call.
    inner = Stream([1, 2, 3])
    inner.map(lambda x: x)  # extends inner, consuming this reference

    with pytest.raises(IllegalStateException):
        Stream(inner)


@pytest.mark.asyncio
async def test_inner_stream_handlers_survive_outer_exhaustion(mocker) -> None:
    # Pins stream-close-handling's "A stream consumed as another stream's
    # source does not fire its close handlers": _accept()/_maybe_aclose()
    # must not treat consuming a Stream-as-source as closing it.
    handler = mocker.Mock()
    inner = Stream([1, 2, 3]).on_close(handler)

    it = await Stream(inner).collect(to_list())

    handler.assert_not_called()
    assert it == [1, 2, 3]


@pytest.mark.asyncio
async def test_inner_stream_handlers_survive_short_circuited_outer(mocker) -> None:
    # Same pin as above, but under a short-circuiting terminal rather than
    # exhaustion - see _accept()/_maybe_aclose().
    handler = mocker.Mock()
    inner = Stream([1, 2, 3]).on_close(handler)
    outer = Stream(inner)

    await outer.find_any()

    handler.assert_not_called()

    # then: closing the inner stream still runs its handler exactly once
    inner.close()
    handler.assert_called_once()


@pytest.mark.asyncio
async def test_autoclose_simple(mocker, monkeypatch, int_2_letter):
    # given
    stream = Stream([1, 2, 3, 4, 1, 2, 3, 4])
    close_mock = mocker.Mock()
    monkeypatch.setattr(stream, "close", close_mock)

    # when
    with closing(stream) as stream:
        it = await stream.map(lambda x: int_2_letter[x]).distinct().collect(to_list())

    # then
    close_mock.assert_called_once()
    assert len(it) == 4
