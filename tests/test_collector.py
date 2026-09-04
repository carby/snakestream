import asyncio
import pytest

from snakestream import Stream
from snakestream.collector import Characteristics, Collector, to_generator
from snakestream.collectors import grouping_by, partitioning_by, summing_int, to_list
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
    exercises CollectorSink's own one-time dispatch safety net."""

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
async def test_collector_combiner_invoked_parallel() -> None:
    # make-combiners-live: a Collector supplying a combiner is partitioned
    # under .parallel() (task 1.1's protocol via CollectorSink), so this is
    # now the case that exercises it rather than the case that forbids it.
    calls = 0

    def combiner(a: list, b: list) -> list:
        nonlocal calls
        calls += 1
        a.extend(b)
        return a

    collector = Collector(list, lambda c, e: c.append(e), combiner=combiner)
    actual = await Stream.of(list(range(50))).parallel().collect(collector)
    assert sorted(actual) == list(range(50))
    assert calls > 0


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
    result = await Stream.of([1, 2, 3, 4, 5]).collect(grouping_by(lambda x: x % 2, to_list()))
    result[1].append(999)
    assert result[0] == [2, 4]


@pytest.mark.asyncio
async def test_partitioning_by_downstream_containers_are_isolated() -> None:
    result = await Stream.of([1, 2, 3, 4, 5]).collect(partitioning_by(lambda x: x % 2 == 0, to_list()))
    result[True].append(999)
    assert result[False] == [1, 3, 5]


@pytest.mark.asyncio
async def test_to_list_is_a_factory() -> None:
    # when
    actual = await Stream.of([1, 2, 3]).collect(to_list())
    # then
    assert actual == [1, 2, 3]


@pytest.mark.asyncio
async def test_collect_rejects_the_bare_to_list_name() -> None:
    # given: to_list is a factory, so the bare name is a function, not a
    # Collector - the break is loud, by the same rule that rejects any other
    # plain callable
    stream = Stream.of([1, 2, 3])

    # when / then
    with pytest.raises(StreamBuildException):
        await stream.collect(to_list)


@pytest.mark.asyncio
async def test_one_to_list_collector_is_reusable_across_collections() -> None:
    # given: a Collector holds no per-collection state, so a single returned
    # instance still feeds two independent collections
    collector = to_list()

    # when
    first = await Stream.of([1, 2, 3]).collect(collector)
    second = await Stream.of([4, 5]).collect(collector)

    # then
    assert first == [1, 2, 3]
    assert second == [4, 5]


@pytest.mark.asyncio
async def test_grouping_by_default_downstream_still_builds_lists() -> None:
    # when
    actual = await Stream.of([1, 2, 3, 4, 5]).collect(grouping_by(lambda x: x % 2))
    # then
    assert actual == {1: [1, 3, 5], 0: [2, 4]}


@pytest.mark.asyncio
async def test_partitioning_by_default_downstream_still_builds_lists() -> None:
    # when
    actual = await Stream.of([1, 2, 3, 4]).collect(partitioning_by(lambda x: x % 2 == 0))
    # then
    assert actual == {False: [1, 3], True: [2, 4]}


def test_characteristics_exposes_unordered() -> None:
    assert Characteristics.UNORDERED in Characteristics


def test_characteristics_does_not_define_identity_finish_or_concurrent() -> None:
    assert not hasattr(Characteristics, "IDENTITY_FINISH")
    assert not hasattr(Characteristics, "CONCURRENT")


@pytest.mark.asyncio
async def test_collector_without_characteristics_reports_empty_set() -> None:
    collector = Collector(list, lambda c, e: c.append(e))
    assert collector.characteristics == frozenset()
    assert await Stream.of([1, 2, 3]).collect(collector) == [1, 2, 3]


@pytest.mark.asyncio
async def test_collector_with_unordered_reports_it_and_collects_unchanged() -> None:
    collector = Collector(list, lambda c, e: c.append(e), characteristics=(Characteristics.UNORDERED,))
    assert collector.characteristics == frozenset({Characteristics.UNORDERED})
    assert await Stream.of([1, 2, 3]).collect(collector) == [1, 2, 3]


def test_collector_characteristics_normalizes_list_to_frozenset() -> None:
    collector = Collector(list, lambda c, e: c.append(e), characteristics=[Characteristics.UNORDERED])
    assert collector.characteristics == frozenset({Characteristics.UNORDERED})


def test_collector_characteristics_normalizes_set_to_frozenset() -> None:
    collector = Collector(list, lambda c, e: c.append(e), characteristics={Characteristics.UNORDERED})
    assert collector.characteristics == frozenset({Characteristics.UNORDERED})


def test_collector_characteristics_normalizes_frozenset_to_frozenset() -> None:
    collector = Collector(list, lambda c, e: c.append(e), characteristics=frozenset({Characteristics.UNORDERED}))
    assert collector.characteristics == frozenset({Characteristics.UNORDERED})
