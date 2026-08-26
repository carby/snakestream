from collections.abc import AsyncGenerator
import pytest

from snakestream import Stream
from snakestream.collector import to_generator
from snakestream.collectors import to_list


async def async_generator() -> AsyncGenerator:
    for i in range(1, 6):
        yield i


class _AsyncIteratorNoAclose:
    """A bare async iterator with no aclose(), unlike an async generator."""

    def __init__(self, end: int) -> None:
        self._end = end
        self._i = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._i >= self._end:
            raise StopAsyncIteration
        self._i += 1
        return self._i


@pytest.mark.asyncio
async def test_to_list_simple() -> None:
    # to_list() is a Collector, not a bare callable: only usable via collect()
    # when
    actual = await Stream.of(async_generator()).collect(to_list())
    # then
    assert actual == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_to_generator_simple() -> None:
    # when
    actual = to_generator(async_generator())
    # then
    assert await actual.__anext__() == 1
    assert await actual.__anext__() == 2
    assert await actual.__anext__() == 3
    assert await actual.__anext__() == 4
    assert await actual.__anext__() == 5

    with pytest.raises(StopAsyncIteration):
        await actual.__anext__()


@pytest.mark.asyncio
async def test_to_generator_no_aclose_on_source() -> None:
    # when
    actual = to_generator(_AsyncIteratorNoAclose(3))
    # then
    assert [n async for n in actual] == [1, 2, 3]


@pytest.mark.asyncio
async def test_to_generator() -> None:
    # when
    it = Stream.of([1, 2, 3, 4]).collect(to_generator)
    # then
    assert await it.__anext__() == 1
    assert await it.__anext__() == 2
    assert await it.__anext__() == 3
    assert await it.__anext__() == 4

    with pytest.raises(StopAsyncIteration):
        await it.__anext__()


@pytest.mark.asyncio
async def test_to_generator_with_null_in_stream() -> None:
    # when
    it = Stream.of([1, 2, None, 4]).collect(to_generator)
    # then
    assert await it.__anext__() == 1
    assert await it.__anext__() == 2
    assert await it.__anext__() is None
    assert await it.__anext__() == 4

    with pytest.raises(StopAsyncIteration):
        await it.__anext__()


@pytest.mark.asyncio
async def test_to_generator_with_empty_list_input() -> None:
    # when
    it = Stream.of([]).collect(to_generator)
    # then
    with pytest.raises(StopAsyncIteration):
        await it.__anext__()


@pytest.mark.asyncio
async def test_to_list() -> None:
    # when
    it = await Stream.of([1, 2, 3, 4]).collect(to_list())
    # then
    assert it == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_to_list_with_none_in_stream() -> None:
    # when
    it = await Stream.of([1, None, 3, 4]).collect(to_list())
    # then
    assert it == [1, None, 3, 4]


@pytest.mark.asyncio
async def test_to_list_with_empty_list_input() -> None:
    # when
    it = await Stream.of([]).collect(to_list())
    # then
    assert it == []


@pytest.mark.asyncio
async def test_collect_supplier_accumulator_combiner_sync() -> None:
    # when
    it = await Stream.of([1, 2, 3]).collect(list, list.append, list.extend)
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
    it = await Stream.of([1, 2, 3]).collect(async_supplier, async_accumulator, list.extend)
    # then
    assert it == [1, 2, 3]


@pytest.mark.asyncio
async def test_collect_supplier_accumulator_combiner_empty_stream() -> None:
    # when
    it = await Stream.of([]).collect(list, list.append, list.extend)
    # then
    assert it == []


@pytest.mark.asyncio
async def test_collect_supplier_accumulator_combiner_never_calls_combiner() -> None:
    # given
    combiner_calls: list = []

    def combiner(a: list, b: list) -> None:
        combiner_calls.append((a, b))

    # when
    it = await Stream.of([1, 2, 3]).collect(list, list.append, combiner)
    # then
    assert it == [1, 2, 3]
    assert combiner_calls == []


@pytest.mark.asyncio
async def test_collect_supplier_accumulator_combiner_parallel_never_calls_combiner() -> None:
    # given
    combiner_calls: list = []

    def combiner(a: list, b: list) -> None:
        combiner_calls.append((a, b))

    # when
    it = await Stream.of([1, 2, 3, 4, 5]).parallel().collect(list, list.append, combiner)
    # then
    assert sorted(it) == [1, 2, 3, 4, 5]
    assert combiner_calls == []
