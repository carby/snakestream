import asyncio
from collections import OrderedDict

import pytest

from snakestream.collector import Characteristics
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


# --- what the two forms declare ---------------------------------------------


def test_to_map_without_a_merge_function_declares_unordered() -> None:
    # given the form whose result is a function of the element multiset alone
    # then it declares the mark that lets a racing collect() skip the barrier
    assert Characteristics.UNORDERED in to_map(len, str.upper).characteristics


def test_to_map_with_a_merge_function_does_not_declare_unordered() -> None:
    # given a merge that keeps whichever value arrived first, which is why this
    # form can never declare: the surviving value is chosen by arrival order
    def keep_first(a: str, b: str) -> str:
        return a

    # then
    assert Characteristics.UNORDERED not in to_map(len, str.upper, keep_first).characteristics


@pytest.mark.asyncio
async def test_to_map_without_a_merge_function_is_equal_under_any_ordering() -> None:
    """The declaration above is true of the behaviour, not merely asserted."""
    # given the same elements in two orders, with no key collision
    forwards = await Stream.of(["a", "bb", "ccc"]).collect(to_map(len, str.upper))
    backwards = await Stream.of(["ccc", "bb", "a"]).collect(to_map(len, str.upper))

    # then the collected dicts compare equal, whatever order they were built in
    assert forwards == backwards


@pytest.mark.asyncio
async def test_to_map_with_a_map_supplier_returns_the_callers_type() -> None:
    # given the 4-arg form, whose fourth argument chooses the result container
    result = await Stream.of([1, 2, 3]).collect(to_map(lambda x: x, lambda x: x * x, lambda a, b: b, OrderedDict))

    # then the caller's mapping reaches the caller intact, not copied into a dict
    assert isinstance(result, OrderedDict)
    assert result == {1: 1, 2: 4, 3: 9}


@pytest.mark.asyncio
async def test_to_map_calls_its_map_supplier_once_per_collection() -> None:
    # given one collector instance reused across two collections
    collector = to_map(lambda x: x, lambda x: x, lambda a, b: b, OrderedDict)

    # when
    first = await Stream.of([1, 2]).collect(collector)
    second = await Stream.of([3]).collect(collector)

    # then each collection got its own mapping, unaffected by the other's elements
    assert first is not second
    assert first == {1: 1, 2: 2}
    assert second == {3: 3}


@pytest.mark.asyncio
async def test_to_map_with_a_map_supplier_over_an_empty_stream() -> None:
    # when
    result = await Stream.of([]).collect(to_map(lambda x: x, lambda x: x, lambda a, b: b, OrderedDict))

    # then the caller's type survives even with nothing to put in it
    assert isinstance(result, OrderedDict)
    assert result == {}


@pytest.mark.asyncio
async def test_to_map_merges_duplicate_keys_into_the_callers_mapping() -> None:
    # when a collision is resolved by the merge the 4-arg form always carries
    result = await Stream.of(["a", "aa", "b"]).collect(to_map(len, lambda x: x, lambda a, b: a + b, OrderedDict))

    # then
    assert isinstance(result, OrderedDict)
    assert result == {1: "ab", 2: "aa"}


@pytest.mark.asyncio
async def test_to_map_awaits_an_async_map_supplier() -> None:
    # given a supplier that has to be awaited before it yields a container
    async def supply() -> OrderedDict[int, int]:
        await asyncio.sleep(0)
        return OrderedDict()

    # when
    result = await Stream.of([1, 2]).collect(to_map(lambda x: x, lambda x: x, lambda a, b: b, supply))

    # then
    assert isinstance(result, OrderedDict)
    assert result == {1: 1, 2: 2}


def test_to_map_with_a_map_supplier_does_not_declare_unordered() -> None:
    # given the 4-arg form, which always carries a merge_function - so the
    # container never reaches the characteristics decision, the merge having
    # already excluded the mark
    assert Characteristics.UNORDERED not in to_map(len, str.upper, lambda a, b: b, OrderedDict).characteristics

    # and the no-merge form is untouched by the new overload
    assert Characteristics.UNORDERED in to_map(len, str.upper).characteristics
