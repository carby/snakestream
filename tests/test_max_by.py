import asyncio

import pytest

from snakestream.collector import Characteristics
from snakestream.collectors import max_by
from conftest import TIE_SOURCE, TIED_EARLY, by_key, overtaken
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_max_by_selects_largest_element() -> None:
    # when
    result = await Stream.of([3, 1, 2]).collect(max_by(lambda a, b: a - b))

    # then
    assert result == 3


@pytest.mark.asyncio
async def test_max_by_empty_stream_returns_none() -> None:
    # when
    result = await Stream.of([]).collect(max_by(lambda a, b: a - b))

    # then
    assert result is None


@pytest.mark.asyncio
async def test_max_by_keeps_first_of_tied_elements() -> None:
    input_list = [("a", 5), ("b", 5)]

    # when
    result = await Stream.of(input_list).collect(max_by(lambda x, y: x[1] - y[1]))

    # then
    assert result == ("a", 5)


@pytest.mark.asyncio
async def test_max_by_async_comparator_is_awaited() -> None:
    async def async_comparator(x: int, y: int) -> int:
        await asyncio.sleep(0.01)
        return x - y

    # when
    result = await Stream.of([3, 1, 2]).collect(max_by(async_comparator))

    # then
    assert result == 3


@pytest.mark.asyncio
async def test_max_by_rejects_bool_comparator() -> None:
    # when / then
    with pytest.raises(TypeError):
        await Stream.of([3, 1, 2]).collect(max_by(lambda x, y: x > y))


# --- the collector form and the stream form agree ---------------------------
#
# The mirror of test_min_by.py's trio; see conftest for the source and
# collector-min-max for the requirement.


@pytest.mark.asyncio
async def test_max_by_declares_no_unordered_characteristic() -> None:
    # then: the mark would skip the barrier, and the tie-break needs it
    assert Characteristics.UNORDERED not in max_by(by_key).characteristics


@pytest.mark.asyncio
@pytest.mark.parametrize("run", range(3))
async def test_ordered_racing_max_by_keeps_the_first_of_tied_elements(run) -> None:
    # when
    it = await Stream.of(TIE_SOURCE).parallel().map(overtaken).collect(max_by(by_key))

    # then
    assert it == TIED_EARLY


@pytest.mark.asyncio
async def test_the_collector_form_agrees_with_the_stream_form() -> None:
    # when
    collected = await Stream.of(TIE_SOURCE).parallel().map(overtaken).collect(max_by(by_key))
    reduced = await Stream.of(TIE_SOURCE).parallel().map(overtaken).max(by_key)

    # then
    assert collected == reduced == TIED_EARLY
