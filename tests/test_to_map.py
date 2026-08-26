import asyncio

import pytest

from snakestream.collectors import to_map
from snakestream.exception import IllegalStateException
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_to_map_builds_dict_from_key_and_value_mappers() -> None:
    # when
    result = await Stream.of([1, 2, 3]).collect(to_map(lambda x: x, lambda x: x * x))

    # then
    assert result == {1: 1, 2: 4, 3: 9}


@pytest.mark.asyncio
async def test_to_map_empty_stream_returns_empty_dict() -> None:
    # when
    result = await Stream.of([]).collect(to_map(lambda x: x, lambda x: x))

    # then
    assert result == {}


@pytest.mark.asyncio
async def test_to_map_async_key_mapper_and_value_mapper_are_awaited() -> None:
    async def async_key(x: str) -> int:
        await asyncio.sleep(0.01)
        return len(x)

    async def async_value(x: str) -> str:
        await asyncio.sleep(0.01)
        return x.upper()

    # when
    result = await Stream.of(["a", "bb"]).collect(to_map(async_key, async_value))

    # then
    assert result == {1: "A", 2: "BB"}


@pytest.mark.asyncio
async def test_to_map_duplicate_key_without_merge_function_raises_illegal_state_exception() -> None:
    # when / then
    with pytest.raises(IllegalStateException):
        await Stream.of(["a", "aa", "b"]).collect(to_map(len, lambda x: x))


@pytest.mark.asyncio
async def test_to_map_duplicate_key_is_resolved_via_merge_function() -> None:
    # when
    result = await Stream.of(["a", "aa", "b"]).collect(to_map(len, lambda x: x, lambda a, b: a + b))

    # then
    assert result == {1: "ab", 2: "aa"}


@pytest.mark.asyncio
async def test_to_map_async_merge_function_is_awaited() -> None:
    async def async_merge(a: str, b: str) -> str:
        await asyncio.sleep(0.01)
        return a + b

    # when
    result = await Stream.of(["a", "aa", "b"]).collect(to_map(len, lambda x: x, async_merge))

    # then
    assert result == {1: "ab", 2: "aa"}


@pytest.mark.asyncio
async def test_to_map_merge_function_never_called_when_no_collision() -> None:
    calls = []

    def merge(a: int, b: int) -> int:
        calls.append((a, b))
        return a + b

    # when
    result = await Stream.of([1, 2, 3]).collect(to_map(lambda x: x, lambda x: x, merge))

    # then
    assert result == {1: 1, 2: 2, 3: 3}
    assert calls == []


@pytest.mark.asyncio
async def test_to_map_sync_key_mapper_with_async_value_mapper() -> None:
    """key_mapper and value_mapper are classified independently."""

    async def async_value(x: str) -> str:
        await asyncio.sleep(0.01)
        return x.upper()

    # when
    result = await Stream.of(["a", "bb"]).collect(to_map(len, async_value))

    # then
    assert result == {1: "A", 2: "BB"}


@pytest.mark.asyncio
async def test_to_map_async_key_mapper_with_sync_value_mapper() -> None:
    async def async_key(x: str) -> int:
        await asyncio.sleep(0.01)
        return len(x)

    # when
    result = await Stream.of(["a", "bb"]).collect(to_map(async_key, str.upper))

    # then
    assert result == {1: "A", 2: "BB"}


@pytest.mark.asyncio
async def test_to_map_sync_mappers_with_async_merge_function() -> None:
    """The merge function is classified separately from both mappers."""

    async def async_merge(a: str, b: str) -> str:
        await asyncio.sleep(0.01)
        return a + b

    # when
    result = await Stream.of(["a", "aa", "b"]).collect(to_map(len, str.upper, async_merge))

    # then
    assert result == {1: "AB", 2: "AA"}
