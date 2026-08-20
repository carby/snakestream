import asyncio
import pytest

from snakestream import Stream
from snakestream.collector import Collector, grouping_by, partitioning_by, summing_int, to_generator, to_list
from snakestream.exception import StreamBuildException


@pytest.mark.asyncio
async def test_user_defined_collector_all_sync() -> None:
    actual = await Stream.of([1, 2, 3]).collect(Collector(list, lambda c, e: c.append(e)))
    assert actual == [1, 2, 3]


@pytest.mark.asyncio
async def test_user_defined_collector_all_async() -> None:
    async def supplier() -> list:
        return []

    async def accumulator(container: list, element: int) -> None:
        container.append(element)

    async def finisher(container: list) -> int:
        return len(container)

    actual = await Stream.of([1, 2, 3]).collect(Collector(supplier, accumulator, finisher=finisher))
    assert actual == 3


@pytest.mark.asyncio
async def test_collector_without_finisher_returns_container() -> None:
    actual = await Stream.of([1, 2, 3]).collect(Collector(list, lambda c, e: c.append(e)))
    assert actual == [1, 2, 3]


@pytest.mark.asyncio
async def test_collector_finisher_changes_result_type() -> None:
    actual = await Stream.of([1, 2, 3]).collect(Collector(list, lambda c, e: c.append(e), finisher=len))
    assert actual == 3


@pytest.mark.asyncio
async def test_collector_accumulator_return_value_is_ignored() -> None:
    def accumulate(container: list, element: int) -> str:
        container.append(element)
        return "ignored"

    actual = await Stream.of([1, 2, 3]).collect(Collector(list, accumulate))
    assert actual == [1, 2, 3]


class _SyncCallReturningCoroutineAccumulator:
    """__call__ is plain `def` but its body returns a coroutine object -
    exercises _CollectorSink's own one-time dispatch safety net."""

    def __call__(self, container: list, element: int):
        return self._append(container, element)

    async def _append(self, container: list, element: int) -> None:
        await asyncio.sleep(0.01)
        container.append(element)


@pytest.mark.asyncio
async def test_collector_accumulator_sync_call_returning_coroutine() -> None:
    actual = await Stream.of([1, 2, 3]).collect(Collector(list, _SyncCallReturningCoroutineAccumulator()))
    assert actual == [1, 2, 3]


@pytest.mark.asyncio
async def test_collector_instance_reused_sequentially() -> None:
    collector = Collector(list, lambda c, e: c.append(e))
    first = await Stream.of([1, 2, 3]).collect(collector)
    second = await Stream.of([4, 5]).collect(collector)
    assert first == [1, 2, 3]
    assert second == [4, 5]


@pytest.mark.asyncio
async def test_collector_instance_reused_concurrently() -> None:
    collector = Collector(list, lambda c, e: c.append(e))
    first, second = await asyncio.gather(
        Stream.of([1, 2, 3]).collect(collector),
        Stream.of([4, 5, 6]).collect(collector),
    )
    assert first == [1, 2, 3]
    assert second == [4, 5, 6]


@pytest.mark.asyncio
async def test_collector_instance_reused_on_parallel_stream() -> None:
    collector = Collector(list, lambda c, e: c.append(e))
    actual = await Stream.of([1, 2, 3, 4]).parallel().collect(collector)
    assert sorted(actual) == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_collector_combiner_not_invoked_sequential() -> None:
    def raising_combiner(a: list, b: list) -> list:
        raise AssertionError("combiner must not be called")

    collector = Collector(list, lambda c, e: c.append(e), combiner=raising_combiner)
    actual = await Stream.of([1, 2, 3]).collect(collector)
    assert actual == [1, 2, 3]


@pytest.mark.asyncio
async def test_collector_combiner_not_invoked_parallel() -> None:
    def raising_combiner(a: list, b: list) -> list:
        raise AssertionError("combiner must not be called")

    collector = Collector(list, lambda c, e: c.append(e), combiner=raising_combiner)
    actual = await Stream.of([1, 2, 3, 4]).parallel().collect(collector)
    assert sorted(actual) == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_collect_rejects_plain_callable() -> None:
    consumed = False

    async def not_a_collector(composition):
        nonlocal consumed
        consumed = True
        return [x async for x in composition]

    with pytest.raises(StreamBuildException):
        await Stream.of([1, 2, 3]).collect(not_a_collector)
    assert consumed is False


@pytest.mark.asyncio
async def test_grouping_by_rejects_non_collector_downstream() -> None:
    async def not_a_collector(composition):
        return [x async for x in composition]

    with pytest.raises(StreamBuildException):
        grouping_by(lambda x: x, not_a_collector)


@pytest.mark.asyncio
async def test_partitioning_by_rejects_non_collector_downstream() -> None:
    async def not_a_collector(composition):
        return [x async for x in composition]

    with pytest.raises(StreamBuildException):
        partitioning_by(lambda x: x % 2 == 0, not_a_collector)


@pytest.mark.asyncio
async def test_grouping_by_with_async_accumulator_downstream() -> None:
    result = await Stream.of([1, 2, 3, 4, 5]).collect(grouping_by(lambda x: x % 2, summing_int(lambda x: x)))
    assert result == {1: 9, 0: 6}


@pytest.mark.asyncio
async def test_collect_to_generator_is_not_awaited() -> None:
    it = Stream.of([1, 2, 3]).collect(to_generator)
    assert [x async for x in it] == [1, 2, 3]


@pytest.mark.asyncio
async def test_to_generator_directly_callable() -> None:
    async def source():
        for i in [1, 2, 3]:
            yield i

    it = to_generator(source())
    assert [x async for x in it] == [1, 2, 3]


@pytest.mark.asyncio
async def test_grouping_by_downstream_containers_are_isolated() -> None:
    result = await Stream.of([1, 2, 3, 4, 5]).collect(grouping_by(lambda x: x % 2, to_list))
    result[1].append(999)
    assert result[0] == [2, 4]


@pytest.mark.asyncio
async def test_partitioning_by_downstream_containers_are_isolated() -> None:
    result = await Stream.of([1, 2, 3, 4, 5]).collect(partitioning_by(lambda x: x % 2 == 0, to_list))
    result[True].append(999)
    assert result[False] == [1, 3, 5]
