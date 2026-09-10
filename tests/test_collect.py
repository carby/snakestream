from collections.abc import AsyncGenerator
import pytest

from snakestream import Stream
from snakestream.collector import Characteristics
from snakestream.collectors import joining, to_list, to_set


async def async_generator() -> AsyncGenerator:
    for i in range(1, 6):
        yield i


@pytest.mark.asyncio
async def test_to_list_simple() -> None:
    # to_list() is a Collector, not a bare callable: only usable via collect()
    # when
    actual = await Stream(async_generator()).collect(to_list())
    # then
    assert actual == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_to_list() -> None:
    # when
    it = await Stream([1, 2, 3, 4]).collect(to_list())
    # then
    assert it == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_to_list_with_none_in_stream() -> None:
    # when
    it = await Stream([1, None, 3, 4]).collect(to_list())
    # then
    assert it == [1, None, 3, 4]


@pytest.mark.asyncio
async def test_to_list_with_empty_list_input() -> None:
    # when
    it = await Stream([]).collect(to_list())
    # then
    assert it == []


@pytest.mark.asyncio
async def test_collect_supplier_accumulator_combiner_sync() -> None:
    # when
    it = await Stream([1, 2, 3]).collect(list, list.append, list.extend)
    # then
    assert it == [1, 2, 3]


@pytest.mark.asyncio
async def test_collect_supplier_accumulator_combiner_async() -> None:
    # given
    async def async_supplier() -> list:
        return []

    async def async_accumulator(container: list, item: int) -> None:
        container.append(item)

    # when
    it = await Stream([1, 2, 3]).collect(async_supplier, async_accumulator, list.extend)
    # then
    assert it == [1, 2, 3]


@pytest.mark.asyncio
async def test_collect_supplier_accumulator_combiner_empty_stream() -> None:
    # when
    it = await Stream([]).collect(list, list.append, list.extend)
    # then
    assert it == []


@pytest.mark.asyncio
async def test_collect_supplier_accumulator_combiner_never_calls_combiner() -> None:
    # given
    combiner_calls: list = []

    def combiner(a: list, b: list) -> None:
        combiner_calls.append((a, b))

    # when
    it = await Stream([1, 2, 3]).collect(list, list.append, combiner)
    # then
    assert it == [1, 2, 3]
    assert combiner_calls == []


@pytest.mark.asyncio
async def test_collect_supplier_accumulator_combiner_parallel_invokes_combiner() -> None:
    # make-combiners-live: under .parallel(), the fork-join executor
    # partitions a collect() it can (task 3.1) and the combiner merges each
    # batch's container into the next - live, where it used to be inert.
    combiner_calls = 0

    def combiner(a: list, b: list) -> list:
        nonlocal combiner_calls
        combiner_calls += 1
        a.extend(b)
        return a

    # given a source spanning several batches
    it = await Stream(list(range(50))).parallel().collect(list, list.append, combiner)
    # then
    assert sorted(it) == list(range(50))
    assert combiner_calls > 0


@pytest.mark.asyncio
async def test_collect_supplier_accumulator_combiner_accepts_javas_biconsumer_convention() -> None:
    # Java's Stream.collect(Supplier, BiConsumer, BiConsumer) declares its
    # combiner as a mutating BiConsumer<R,R> - list.extend is Java's own
    # documented example - unlike Collector.combiner()'s returning
    # BinaryOperator<A>. Both conventions must work here: a combiner
    # returning None is read as "the container was mutated in place".
    it = await Stream(list(range(50))).parallel().collect(list, list.append, list.extend)
    assert sorted(it) == list(range(50))


def test_to_set_reports_unordered() -> None:
    assert to_set().characteristics == frozenset({Characteristics.UNORDERED})


def test_to_list_and_joining_do_not_report_unordered() -> None:
    assert Characteristics.UNORDERED not in to_list().characteristics
    assert Characteristics.UNORDERED not in joining().characteristics


@pytest.mark.asyncio
async def test_to_set_declaration_matches_behaviour_across_orderings() -> None:
    # when
    forward = await Stream([1, 2, 3]).collect(to_set())
    backward = await Stream([3, 2, 1]).collect(to_set())
    # then
    assert forward == backward
