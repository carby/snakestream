import asyncio

import pytest

from snakestream import Stream
from snakestream.callable_dispatch import _maybe_await
from snakestream.collector import to_list


def _sync_double(x: int) -> int:
    return x * 2


async def _async_double(x: int) -> int:
    await asyncio.sleep(0.01)
    return x * 2


class SyncCallableDouble:
    def __call__(self, x: int) -> int:
        return x * 2


class AsyncCallableDouble:
    async def __call__(self, x: int) -> int:
        await asyncio.sleep(0.01)
        return x * 2


class AsyncCallablePredicate:
    async def __call__(self, x: int) -> bool:
        await asyncio.sleep(0.01)
        return x % 2 == 0


class AsyncCallableComparator:
    async def __call__(self, a: int, b: int) -> int:
        await asyncio.sleep(0.01)
        return (a > b) - (a < b)


class AsyncCallableAccumulator:
    async def __call__(self, acc: int, x: int) -> int:
        await asyncio.sleep(0.01)
        return acc + x


@pytest.mark.asyncio
async def test_maybe_await_sync_function() -> None:
    assert await _maybe_await(_sync_double, 3) == 6


@pytest.mark.asyncio
async def test_maybe_await_async_function() -> None:
    assert await _maybe_await(_async_double, 3) == 6


@pytest.mark.asyncio
async def test_maybe_await_sync_callable_object() -> None:
    assert await _maybe_await(SyncCallableDouble(), 3) == 6


@pytest.mark.asyncio
async def test_maybe_await_async_callable_object() -> None:
    assert await _maybe_await(AsyncCallableDouble(), 3) == 6


@pytest.mark.asyncio
async def test_map_async_callable_object() -> None:
    actual = await Stream.of([1, 2, 3]).map(AsyncCallableDouble()).collect(to_list)
    assert actual == [2, 4, 6]


@pytest.mark.asyncio
async def test_filter_async_callable_object() -> None:
    actual = await Stream.of([1, 2, 3, 4]).filter(AsyncCallablePredicate()).collect(to_list)
    assert actual == [2, 4]


class _RecordingAsyncCallableConsumer:
    def __init__(self) -> None:
        self.seen: list[int] = []

    async def __call__(self, x: int) -> None:
        await asyncio.sleep(0.01)
        self.seen.append(x)


@pytest.mark.asyncio
async def test_peek_async_callable_object() -> None:
    consumer = _RecordingAsyncCallableConsumer()
    actual = await Stream.of([1, 2, 3]).peek(consumer).collect(to_list)
    assert actual == [1, 2, 3]
    assert consumer.seen == [1, 2, 3]


@pytest.mark.asyncio
async def test_reduce_async_callable_object() -> None:
    actual = await Stream.of([1, 2, 3]).reduce(0, AsyncCallableAccumulator())
    assert actual == 6


@pytest.mark.asyncio
async def test_for_each_async_callable_object() -> None:
    consumer = _RecordingAsyncCallableConsumer()
    await Stream.of([1, 2, 3]).for_each(consumer)
    assert consumer.seen == [1, 2, 3]


@pytest.mark.asyncio
async def test_sorted_async_callable_object_comparator() -> None:
    actual = await Stream.of([3, 1, 2]).sorted(comparator=AsyncCallableComparator()).collect(to_list)
    assert actual == [1, 2, 3]


@pytest.mark.asyncio
async def test_min_async_callable_object_comparator() -> None:
    actual = await Stream.of([3, 1, 2]).min(AsyncCallableComparator())
    assert actual == 1


@pytest.mark.asyncio
async def test_max_async_callable_object_comparator() -> None:
    actual = await Stream.of([3, 1, 2]).max(AsyncCallableComparator())
    assert actual == 3


@pytest.mark.asyncio
async def test_all_match_async_callable_object() -> None:
    actual = await Stream.of([2, 4, 6]).all_match(AsyncCallablePredicate())
    assert actual is True


@pytest.mark.asyncio
async def test_any_match_async_callable_object() -> None:
    actual = await Stream.of([1, 3, 4]).any_match(AsyncCallablePredicate())
    assert actual is True


@pytest.mark.asyncio
async def test_none_match_async_callable_object() -> None:
    actual = await Stream.of([1, 3, 5]).none_match(AsyncCallablePredicate())
    assert actual is True
