import pytest
from snakestream.collector import to_list
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_skip_drops_first_n_of_longer_source() -> None:
    # when
    lst = await Stream.of([0, 1, 2, 3, 4]).skip(2).collect(to_list())

    # then
    assert lst == [2, 3, 4]


@pytest.mark.asyncio
async def test_skip_shorter_than_n_source_yields_nothing() -> None:
    # when
    lst = await Stream.of([0, 1]).skip(5).collect(to_list())

    # then
    assert lst == []


@pytest.mark.asyncio
async def test_skip_zero_is_noop() -> None:
    # when
    lst = await Stream.of([0, 1, 2]).skip(0).collect(to_list())

    # then
    assert lst == [0, 1, 2]


@pytest.mark.asyncio
async def test_skip_exact_size_source_yields_nothing() -> None:
    # when
    lst = await Stream.of([0, 1, 2]).skip(3).collect(to_list())

    # then
    assert lst == []


@pytest.mark.asyncio
async def test_skip_async_source() -> None:
    async def gen():
        for i in range(5):
            yield i

    # when
    lst = await Stream.of(gen()).skip(2).collect(to_list())

    # then
    assert lst == [2, 3, 4]


@pytest.mark.asyncio
async def test_skip_state_not_shared_across_separate_streams() -> None:
    # given: a first stream drains its own skip() counter
    await Stream.of([0, 1, 2]).skip(2).collect(to_list())

    # when: a second, independently-built skip() stream should still drop
    # its own n elements, unaffected by the first stream's counter
    second = await Stream.of([0, 1, 2, 3, 4]).skip(2).collect(to_list())

    # then
    assert second == [2, 3, 4]


@pytest.mark.asyncio
async def test_skip_state_fresh_on_second_composition() -> None:
    # given
    stream = Stream.of([0, 1, 2, 3, 4]).skip(2)
    first = await stream.collect(to_list())

    # when
    second = await stream.collect(to_list())

    # then
    assert first == [2, 3, 4]
    # source is exhausted after the first run, but a second composition must
    # not raise or silently reuse the first run's skipped counter
    assert second == []
