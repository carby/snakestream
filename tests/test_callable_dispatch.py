import asyncio
import functools

import pytest

from snakestream import Stream
from snakestream.callable_dispatch import is_async_callable, maybe_await
from snakestream.collectors import (
    to_list,
    summing_int,
    summing_long,
    summing_double,
    averaging_int,
    averaging_long,
    averaging_double,
    grouping_by,
    partitioning_by,
    reducing,
    to_map,
    min_by,
)


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
    assert await maybe_await(_sync_double, 3) == 6


@pytest.mark.asyncio
async def test_maybe_await_async_function() -> None:
    assert await maybe_await(_async_double, 3) == 6


@pytest.mark.asyncio
async def test_maybe_await_sync_callable_object() -> None:
    assert await maybe_await(SyncCallableDouble(), 3) == 6


@pytest.mark.asyncio
async def test_maybe_await_async_callable_object() -> None:
    assert await maybe_await(AsyncCallableDouble(), 3) == 6


@pytest.mark.asyncio
async def test_map_async_callable_object() -> None:
    actual = await Stream.of([1, 2, 3]).map(AsyncCallableDouble()).collect(to_list())
    assert actual == [2, 4, 6]


@pytest.mark.asyncio
async def test_filter_async_callable_object() -> None:
    actual = await Stream.of([1, 2, 3, 4]).filter(AsyncCallablePredicate()).collect(to_list())
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
    actual = await Stream.of([1, 2, 3]).peek(consumer).collect(to_list())
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
    actual = await Stream.of([3, 1, 2]).sorted(comparator=AsyncCallableComparator()).collect(to_list())
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


# --- 5.1 is_async_callable direct coverage ---


def test_is_async_callable_sync_function() -> None:
    assert is_async_callable(_sync_double) is False


def test_is_async_callable_async_function() -> None:
    assert is_async_callable(_async_double) is True


def test_is_async_callable_sync_callable_object() -> None:
    assert is_async_callable(SyncCallableDouble()) is False


def test_is_async_callable_async_callable_object() -> None:
    assert is_async_callable(AsyncCallableDouble()) is True


def test_is_async_callable_partial_wrapping_sync_function() -> None:
    assert is_async_callable(functools.partial(_sync_double)) is False


def test_is_async_callable_partial_wrapping_async_function() -> None:
    assert is_async_callable(functools.partial(_async_double)) is True


def test_is_async_callable_partial_wrapping_sync_callable_object() -> None:
    assert is_async_callable(functools.partial(SyncCallableDouble())) is False


def test_is_async_callable_partial_wrapping_async_callable_object() -> None:
    # functools.partial's own __call__ is not `async def`, and the wrapped
    # object's async __call__ is one level too deep for the build-time
    # check to see - this is expected to fall back to the first-result
    # isawaitable safety net at runtime rather than being classified async
    # up front (see test_map_partial_wrapping_async_callable_object below).
    assert is_async_callable(functools.partial(AsyncCallableDouble())) is False


# --- 5.2 sync-__call__-returning-a-coroutine regression ---


class _SyncCallReturningCoroutine:
    """__call__ is plain `def` but its body returns a coroutine object."""

    def __call__(self, x: int):
        return self._compute(x)

    async def _compute(self, x: int) -> int:
        await asyncio.sleep(0.01)
        return x * 2


@pytest.mark.asyncio
async def test_map_sync_call_returning_coroutine() -> None:
    actual = await Stream.of([1, 2, 3]).map(_SyncCallReturningCoroutine()).collect(to_list())
    assert actual == [2, 4, 6]


@pytest.mark.asyncio
async def test_filter_sync_call_returning_coroutine() -> None:
    class _EvenPredicateReturningCoroutine:
        def __call__(self, x: int):
            return self._check(x)

        async def _check(self, x: int) -> bool:
            await asyncio.sleep(0.01)
            return x % 2 == 0

    actual = await Stream.of([1, 2, 3, 4]).filter(_EvenPredicateReturningCoroutine()).collect(to_list())
    assert actual == [2, 4]


@pytest.mark.asyncio
async def test_summing_int_sync_call_returning_coroutine() -> None:
    actual = await Stream.of([1, 2, 3]).collect(summing_int(_SyncCallReturningCoroutine()))
    assert actual == 12


@pytest.mark.asyncio
async def test_map_partial_wrapping_async_callable_object() -> None:
    actual = await Stream.of([1, 2, 3]).map(functools.partial(AsyncCallableDouble())).collect(to_list())
    assert actual == [2, 4, 6]


# --- 5.3 classification does not leak across compositions ---


@pytest.mark.asyncio
async def test_map_classification_does_not_leak_across_compositions() -> None:
    # Each composition of an equivalent map(mapper) chain runs the mapper's
    # `is_async`/`checked` locals fresh (they live inside the per-composition
    # generator body) - a prior composition's classification must not
    # persist and corrupt a later, independent one.
    mapper = AsyncCallableDouble()
    first = await Stream.of([1, 2, 3]).map(mapper).collect(to_list())
    second = await Stream.of([4, 5, 6]).map(mapper).collect(to_list())
    assert first == [2, 4, 6]
    assert second == [8, 10, 12]


# --- 5.4 ParallelStream coverage ---


@pytest.mark.asyncio
async def test_parallel_async_callable_object_mapper() -> None:
    actual = await Stream.of([1, 2, 3, 4]).parallel().map(AsyncCallableDouble()).collect(to_list())
    assert sorted(actual) == [2, 4, 6, 8]


# --- 5.6 coverage: exercise the first-result safety net on every remaining
# per-element classification site, via sync-`__call__`-returning-a-coroutine
# callables, so the `elif not checked: ... if isawaitable(...)` arc is
# taken (and confirmed-True) at every call site, not just map/filter/summing_int.


class _SyncCallReturningCoroutineConsumer:
    def __init__(self) -> None:
        self.seen: list[int] = []

    def __call__(self, x: int):
        return self._record(x)

    async def _record(self, x: int) -> None:
        await asyncio.sleep(0.01)
        self.seen.append(x)


class _SyncCallReturningCoroutineBiConsumer:
    def __call__(self, container: list, x: int):
        return self._append(container, x)

    async def _append(self, container: list, x: int) -> None:
        await asyncio.sleep(0.01)
        container.append(x)


class _SyncCallReturningCoroutineAccumulator:
    def __call__(self, acc: int, x: int):
        return self._add(acc, x)

    async def _add(self, acc: int, x: int) -> int:
        await asyncio.sleep(0.01)
        return acc + x


class _SyncCallReturningCoroutineComparator:
    def __call__(self, a: int, b: int):
        return self._compare(a, b)

    async def _compare(self, a: int, b: int) -> int:
        await asyncio.sleep(0.01)
        return (a > b) - (a < b)


class _SyncCallReturningCoroutinePredicate:
    def __call__(self, x: int):
        return self._check(x)

    async def _check(self, x: int) -> bool:
        await asyncio.sleep(0.01)
        return x % 2 == 0


@pytest.mark.asyncio
async def test_peek_sync_call_returning_coroutine() -> None:
    consumer = _SyncCallReturningCoroutineConsumer()
    actual = await Stream.of([1, 2, 3]).peek(consumer).collect(to_list())
    assert actual == [1, 2, 3]
    assert consumer.seen == [1, 2, 3]


@pytest.mark.asyncio
async def test_collect_mutable_sync_call_returning_coroutine() -> None:
    async def supplier() -> list:
        return []

    actual = await Stream.of([1, 2, 3]).collect(supplier, _SyncCallReturningCoroutineBiConsumer(), lambda a, b: a)
    assert actual == [1, 2, 3]


@pytest.mark.asyncio
async def test_reduce_sync_call_returning_coroutine() -> None:
    actual = await Stream.of([1, 2, 3]).reduce(0, _SyncCallReturningCoroutineAccumulator())
    assert actual == 6


@pytest.mark.asyncio
async def test_for_each_sync_call_returning_coroutine() -> None:
    consumer = _SyncCallReturningCoroutineConsumer()
    await Stream.of([1, 2, 3]).for_each(consumer)
    assert consumer.seen == [1, 2, 3]


@pytest.mark.asyncio
async def test_for_each_ordered_sync_call_returning_coroutine() -> None:
    consumer = _SyncCallReturningCoroutineConsumer()
    await Stream.of([1, 2, 3]).for_each_ordered(consumer)
    assert consumer.seen == [1, 2, 3]


@pytest.mark.asyncio
async def test_min_sync_call_returning_coroutine_comparator() -> None:
    actual = await Stream.of([3, 1, 2]).min(_SyncCallReturningCoroutineComparator())
    assert actual == 1


@pytest.mark.asyncio
async def test_all_match_sync_call_returning_coroutine() -> None:
    actual = await Stream.of([2, 4, 6]).all_match(_SyncCallReturningCoroutinePredicate())
    assert actual is True


@pytest.mark.asyncio
async def test_summing_long_sync_call_returning_coroutine() -> None:
    actual = await Stream.of([1, 2, 3]).collect(summing_long(_SyncCallReturningCoroutine()))
    assert actual == 12


@pytest.mark.asyncio
async def test_summing_double_sync_call_returning_coroutine() -> None:
    actual = await Stream.of([1, 2, 3]).collect(summing_double(_SyncCallReturningCoroutine()))
    assert actual == 12.0


@pytest.mark.asyncio
async def test_averaging_int_sync_call_returning_coroutine() -> None:
    actual = await Stream.of([1, 2, 3]).collect(averaging_int(_SyncCallReturningCoroutine()))
    assert actual == 4.0


@pytest.mark.asyncio
async def test_averaging_long_sync_call_returning_coroutine() -> None:
    actual = await Stream.of([1, 2, 3]).collect(averaging_long(_SyncCallReturningCoroutine()))
    assert actual == 4.0


@pytest.mark.asyncio
async def test_averaging_double_sync_call_returning_coroutine() -> None:
    actual = await Stream.of([1, 2, 3]).collect(averaging_double(_SyncCallReturningCoroutine()))
    assert actual == 4.0


@pytest.mark.asyncio
async def test_grouping_by_sync_call_returning_coroutine() -> None:
    actual = await Stream.of([1, 2, 3, 4]).collect(grouping_by(_SyncCallReturningCoroutinePredicate()))
    assert actual == {True: [2, 4], False: [1, 3]}


@pytest.mark.asyncio
async def test_partitioning_by_sync_call_returning_coroutine() -> None:
    actual = await Stream.of([1, 2, 3, 4]).collect(partitioning_by(_SyncCallReturningCoroutinePredicate()))
    assert actual == {True: [2, 4], False: [1, 3]}


@pytest.mark.asyncio
async def test_reducing_sync_call_returning_coroutine() -> None:
    actual = await Stream.of([1, 2, 3]).collect(reducing(0, _SyncCallReturningCoroutineAccumulator()))
    assert actual == 6


@pytest.mark.asyncio
async def test_to_map_sync_call_returning_coroutine() -> None:
    actual = await Stream.of([1, 2]).collect(to_map(_SyncCallReturningCoroutinePredicate(), _SyncCallReturningCoroutine()))
    assert actual == {False: 2, True: 4}


@pytest.mark.asyncio
async def test_min_by_sync_call_returning_coroutine_comparator() -> None:
    actual = await Stream.of([3, 1, 2]).collect(min_by(_SyncCallReturningCoroutineComparator()))
    assert actual == 1


@pytest.mark.asyncio
async def test_sorted_sync_call_returning_coroutine_comparator() -> None:
    actual = await Stream.of([3, 1, 2]).sorted(comparator=_SyncCallReturningCoroutineComparator()).collect(to_list())
    assert actual == [1, 2, 3]
