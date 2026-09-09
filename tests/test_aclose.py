import asyncio

import pytest

from snakestream.collectors import to_list
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_aclose_with_no_handlers_is_a_noop() -> None:
    stream = Stream([1, 2, 3])

    await stream.aclose()


@pytest.mark.asyncio
async def test_aclose_awaits_an_async_handler() -> None:
    ran = []

    async def async_handler() -> None:
        ran.append(True)

    stream = Stream([1, 2, 3])
    stream.on_close(async_handler)

    await stream.aclose()

    assert ran == [True]


@pytest.mark.asyncio
async def test_aclose_runs_sync_handlers_too(mocker) -> None:
    mock_callback1 = mocker.Mock()
    mock_callback2 = mocker.Mock()

    stream = Stream([1, 2, 3])
    stream.on_close(mock_callback1).on_close(mock_callback2)

    await stream.aclose()

    mock_callback1.assert_called_once()
    mock_callback2.assert_called_once()


@pytest.mark.asyncio
async def test_aclose_runs_mixed_handlers_in_registration_order(mocker) -> None:
    calls = []
    sync_a = mocker.Mock(side_effect=lambda: calls.append("sync_a"))
    sync_c = mocker.Mock(side_effect=lambda: calls.append("sync_c"))

    async def async_b() -> None:
        calls.append("async_b")

    stream = Stream([1, 2, 3])
    stream.on_close(sync_a).on_close(async_b).on_close(sync_c)

    await stream.aclose()

    assert calls == ["sync_a", "async_b", "sync_c"]


@pytest.mark.asyncio
async def test_aclose_on_a_consumed_reference_still_closes(mocker) -> None:
    handler = mocker.Mock()
    stream = Stream([1, 2, 3]).on_close(handler)

    derived = stream.map(lambda x: x)
    await derived.collect(to_list())

    await stream.aclose()

    handler.assert_called_once()


@pytest.mark.asyncio
async def test_aclose_does_not_run_handlers_concurrently() -> None:
    events: list[str] = []

    async def first() -> None:
        events.append("first-enter")
        await asyncio.sleep(0)
        events.append("first-exit")

    async def second() -> None:
        events.append("second-enter")
        events.append("second-exit")

    stream = Stream([1, 2, 3])
    stream.on_close(first).on_close(second)

    await stream.aclose()

    assert events == ["first-enter", "first-exit", "second-enter", "second-exit"]


@pytest.mark.asyncio
async def test_aclose_runs_remaining_handlers_after_one_raises(mocker) -> None:
    bad = mocker.Mock(side_effect=ValueError("boom"))
    good = mocker.Mock()

    stream = Stream([1, 2, 3])
    stream.on_close(bad).on_close(good)

    with pytest.raises(ValueError, match="boom"):
        await stream.aclose()

    bad.assert_called_once()
    good.assert_called_once()


@pytest.mark.asyncio
async def test_aclose_treats_a_raise_while_awaited_as_an_ordinary_failure() -> None:
    ran = []

    async def async_bad() -> None:
        await asyncio.sleep(0)
        raise ValueError("boom")

    async def async_good() -> None:
        ran.append(True)

    stream = Stream([1, 2, 3])
    stream.on_close(async_bad).on_close(async_good)

    with pytest.raises(ValueError, match="boom"):
        await stream.aclose()

    assert ran == [True]


@pytest.mark.asyncio
async def test_aclose_with_three_failing_handlers_notes_the_other_two(mocker) -> None:
    bad_a = mocker.Mock(side_effect=ValueError("first"))

    async def bad_b() -> None:
        raise ValueError("second")

    bad_c = mocker.Mock(side_effect=ValueError("third"))

    stream = Stream([1, 2, 3])
    stream.on_close(bad_a).on_close(bad_b).on_close(bad_c)

    with pytest.raises(ValueError, match="first") as exc_info:
        await stream.aclose()

    bad_a.assert_called_once()
    bad_c.assert_called_once()
    assert len(exc_info.value.__notes__) == 2
    assert "second" in exc_info.value.__notes__[0]
    assert "third" in exc_info.value.__notes__[1]


@pytest.mark.asyncio
async def test_aclose_leaves_the_source_alone() -> None:
    async def gen():
        yield 1
        yield 2

    stream = Stream(gen())

    await stream.aclose()

    result = await stream.collect(to_list())
    assert result == [1, 2]
