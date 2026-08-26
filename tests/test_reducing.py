import asyncio

import pytest

from snakestream.collectors import reducing
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_reducing_no_identity_folds_left_from_first_element() -> None:
    # when
    result = await Stream.of([1, 2, 3, 4]).collect(reducing(lambda a, b: a + b))

    # then
    assert result == 10


@pytest.mark.asyncio
async def test_reducing_no_identity_empty_stream_returns_none() -> None:
    # when
    result = await Stream.of([]).collect(reducing(lambda a, b: a + b))

    # then
    assert result is None


@pytest.mark.asyncio
async def test_reducing_no_identity_single_element_short_circuits() -> None:
    calls = []

    def op(a: int, b: int) -> int:
        calls.append((a, b))
        return a + b

    # when
    result = await Stream.of([5]).collect(reducing(op))

    # then
    assert result == 5
    assert calls == []


@pytest.mark.asyncio
async def test_reducing_with_identity_folds_from_identity() -> None:
    # when
    result = await Stream.of([1, 2, 3]).collect(reducing(10, lambda a, b: a + b))

    # then
    assert result == 16


@pytest.mark.asyncio
async def test_reducing_with_identity_empty_stream_returns_identity_unchanged() -> None:
    # when
    result = await Stream.of([]).collect(reducing(10, lambda a, b: a + b))

    # then
    assert result == 10


@pytest.mark.asyncio
async def test_reducing_with_mapper_maps_then_folds() -> None:
    # when
    result = await Stream.of(["a", "bb", "ccc"]).collect(reducing(0, len, lambda a, b: a + b))

    # then
    assert result == 6


@pytest.mark.asyncio
async def test_reducing_with_mapper_empty_stream_returns_identity_unchanged() -> None:
    # when
    result = await Stream.of([]).collect(reducing(0, len, lambda a, b: a + b))

    # then
    assert result == 0


@pytest.mark.asyncio
async def test_reducing_with_mapper_async_mapper_and_operator_are_awaited() -> None:
    async def async_len(s: str) -> int:
        await asyncio.sleep(0.01)
        return len(s)

    async def async_add(a: int, b: int) -> int:
        await asyncio.sleep(0.01)
        return a + b

    # when
    result = await Stream.of(["a", "bb", "ccc"]).collect(reducing(0, async_len, async_add))

    # then
    assert result == 6


@pytest.mark.asyncio
async def test_reducing_no_identity_async_operator_is_awaited() -> None:
    async def async_add(a: int, b: int) -> int:
        await asyncio.sleep(0.01)
        return a + b

    # when
    result = await Stream.of([1, 2, 3, 4]).collect(reducing(async_add))

    # then
    assert result == 10


@pytest.mark.asyncio
async def test_reducing_sync_mapper_with_async_binary_operator() -> None:
    """mapper and binary_operator are classified independently."""

    async def async_add(a: int, b: int) -> int:
        await asyncio.sleep(0.01)
        return a + b

    # when
    result = await Stream.of(["a", "bb", "ccc"]).collect(reducing(0, len, async_add))

    # then
    assert result == 6


@pytest.mark.asyncio
async def test_reducing_async_mapper_with_sync_binary_operator() -> None:
    async def async_len(s: str) -> int:
        await asyncio.sleep(0.01)
        return len(s)

    # when
    result = await Stream.of(["a", "bb", "ccc"]).collect(reducing(0, async_len, lambda a, b: a + b))

    # then
    assert result == 6
