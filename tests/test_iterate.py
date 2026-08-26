from inspect import isawaitable

import pytest

from snakestream.collector import to_generator
from snakestream.collectors import to_list
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_iterate_simple() -> None:
    # when
    it = Stream.iterate(0, lambda n: n + 1).collect(to_generator)

    # then
    assert await it.__anext__() == 0
    assert await it.__anext__() == 1
    assert await it.__anext__() == 2
    assert await it.__anext__() == 3
    assert await it.__anext__() == 4
    assert await it.__anext__() == 5


@pytest.mark.asyncio
async def test_iterate_fib() -> None:
    # when
    it = Stream.iterate((0, 1), lambda n: (n[1], n[0] + n[1])).collect(to_generator)

    # then
    assert (await it.__anext__())[0] == 0
    assert (await it.__anext__())[0] == 1
    assert (await it.__anext__())[0] == 1
    assert (await it.__anext__())[0] == 2
    assert (await it.__anext__())[0] == 3
    assert (await it.__anext__())[0] == 5
    assert (await it.__anext__())[0] == 8
    assert (await it.__anext__())[0] == 13
    assert (await it.__anext__())[0] == 21
    assert (await it.__anext__())[0] == 34
    assert (await it.__anext__())[0] == 55


@pytest.mark.asyncio
async def test_iterate_with_async_def_nxt() -> None:
    # given
    async def nxt(n: int) -> int:
        return n + 1

    # when
    result = await Stream.iterate(0, nxt).limit(3).collect(to_list())

    # then
    assert result == [0, 1, 2]
    assert not any(isawaitable(x) for x in result)


@pytest.mark.asyncio
async def test_iterate_with_sync_callable_object_nxt() -> None:
    # given
    class SyncNxt:
        def __call__(self, n: int) -> int:
            return n + 1

    # when
    result = await Stream.iterate(0, SyncNxt()).limit(3).collect(to_list())

    # then
    assert result == [0, 1, 2]


@pytest.mark.asyncio
async def test_iterate_with_async_callable_object_nxt() -> None:
    # given
    class AsyncNxt:
        async def __call__(self, n: int) -> int:
            return n + 1

    # when
    result = await Stream.iterate(0, AsyncNxt()).limit(3).collect(to_list())

    # then
    assert result == [0, 1, 2]
    assert not any(isawaitable(x) for x in result)


@pytest.mark.asyncio
async def test_iterate_with_sync_signatured_nxt_returning_a_coroutine() -> None:
    # given
    async def _inc(n: int) -> int:
        return n + 1

    def nxt(n: int):  # plain def, but returns a coroutine
        return _inc(n)

    # when
    result = await Stream.iterate(0, nxt).limit(3).collect(to_list())

    # then
    assert result == [0, 1, 2]
    assert not any(isawaitable(x) for x in result)


@pytest.mark.asyncio
async def test_iterate_does_no_work_until_consumed() -> None:
    # given
    calls = 0

    def nxt(n: int) -> int:
        nonlocal calls
        calls += 1
        return n + 1

    # when
    Stream.iterate(0, nxt)

    # then
    assert calls == 0


@pytest.mark.asyncio
async def test_iterate_calls_nxt_exactly_n_minus_1_times() -> None:
    # given
    calls = 0

    def nxt(n: int) -> int:
        nonlocal calls
        calls += 1
        return n + 1

    # when
    result = await Stream.iterate(0, nxt).limit(5).collect(to_list())

    # then
    assert result == [0, 1, 2, 3, 4]
    assert calls == 4


@pytest.mark.asyncio
async def test_iterate_with_async_nxt_composes_like_sync_nxt() -> None:
    # given
    async def async_nxt(n: int) -> int:
        return n + 1

    def sync_nxt(n: int) -> int:
        return n + 1

    # when
    async_result = (
        await Stream.iterate(0, async_nxt).map(lambda x: x * 2).filter(lambda x: x % 4 == 0).limit(3).collect(to_list())
    )
    sync_result = (
        await Stream.iterate(0, sync_nxt).map(lambda x: x * 2).filter(lambda x: x % 4 == 0).limit(3).collect(to_list())
    )

    # then
    assert async_result == sync_result


@pytest.mark.asyncio
async def test_iterate_with_async_nxt_under_parallel() -> None:
    # given
    async def nxt(n: int) -> int:
        return n + 1

    # when
    result = await Stream.iterate(0, nxt).parallel().limit(10).collect(to_list())

    # then
    assert len(result) == 10
    assert not any(isawaitable(x) for x in result)
