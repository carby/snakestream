from collections.abc import AsyncGenerator

import pytest

from snakestream.collector import to_list
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_iterator_returns_async_generator_without_consuming() -> None:
    # given
    pulled = []

    async def source():
        for i in [1, 2, 3]:
            pulled.append(i)
            yield i

    # when
    it = Stream.of(source()).map(lambda x: x).iterator()

    # then
    assert isinstance(it, AsyncGenerator)
    assert pulled == []


@pytest.mark.asyncio
async def test_iterator_yields_same_elements_as_collect() -> None:
    # given
    chain = lambda: Stream.of([1, 2, 3, 4]).map(lambda x: x * 2).filter(lambda x: x > 2)  # noqa: E731

    # when
    from_iterator = [x async for x in chain().iterator()]
    from_collect = await chain().collect(to_list)

    # then
    assert from_iterator == from_collect == [4, 6, 8]


@pytest.mark.asyncio
async def test_iterator_supports_partial_consumption() -> None:
    # when
    it = Stream.of([1, 2, 3, 4, 5]).iterator()
    first = await it.__anext__()
    second = await it.__anext__()

    # then
    assert first == 1
    assert second == 2


@pytest.mark.asyncio
async def test_iterator_on_parallel_stream_yields_expected_elements() -> None:
    # when
    it = [x async for x in Stream.of([1, 2, 3, 4]).parallel().iterator()]

    # then
    assert sorted(it) == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_iterator_does_not_consume_or_mutate_chain() -> None:
    # given
    stream = Stream.of([1, 2, 3]).map(lambda x: x * 2)
    chain_len_before = len(stream._chain)

    # when
    first = [x async for x in stream.iterator()]
    chain_len_after_iterator = len(stream._chain)
    second = await stream.collect(to_list)

    # then
    assert first == [2, 4, 6]
    # the source is a one-shot generator, so the second run legitimately sees
    # nothing further to pull -- what matters is the chain itself wasn't
    # drained by iterator()'s composition.
    assert second == []
    assert chain_len_after_iterator == chain_len_before
    assert len(stream._chain) == chain_len_before
