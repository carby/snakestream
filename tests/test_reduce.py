import asyncio
import functools

import pytest
from hypothesis import given
from hypothesis import strategies as st

from snakestream import Stream
from snakestream.exception import StreamBuildException


@pytest.mark.asyncio
async def test_reducer() -> None:
    # when
    it = Stream([1, 2, 3, 4, 5, 6]).reduce(0, lambda x, y: x + y)
    # then
    assert await it == 21


@pytest.mark.asyncio
async def test_reducer_associative() -> None:
    # when
    it = Stream([1, 2, 3, 4, 5, 6]).reduce(0, lambda x, y: x + y)

    it2 = Stream([1, 2, 3, 4, 5, 6]).reduce(0, lambda x, y: y + x)
    # then
    assert await it == 21
    assert await it2 == 21


@pytest.mark.asyncio
async def test_async_reducer() -> None:
    async def async_reducer(x: int, y: int):
        await asyncio.sleep(0.01)
        return x + y

    # when
    it = Stream([1, 2, 3, 4, 5, 6]).reduce(0, async_reducer)

    # then
    assert await it == 21


@pytest.mark.asyncio
async def test_reducer_mixed_chain(letter_2_int) -> None:
    # when
    it = Stream(["a", "b", "c", "d"]).map(lambda x: letter_2_int[x]).reduce(0, lambda x, y: x + y)
    # then
    assert await it == 10


@given(values=st.lists(st.integers()))
@pytest.mark.asyncio
async def test_reduce_matches_functools_reduce(values: list[int]) -> None:
    accumulator = lambda x, y: x + y  # noqa: E731

    # when
    actual = await Stream(values).reduce(0, accumulator)

    # then
    assert actual == functools.reduce(accumulator, values, 0)


@given(values=st.lists(st.integers()))
@pytest.mark.asyncio
async def test_reduce_async_accumulator_matches_functools_reduce(values: list[int]) -> None:
    async def async_add(x: int, y: int) -> int:
        return x + y

    # when
    actual = await Stream(values).reduce(0, async_add)

    # then
    assert actual == functools.reduce(lambda x, y: x + y, values, 0)


@pytest.mark.asyncio
async def test_reduce_no_identity_empty_stream_returns_none() -> None:
    calls = []

    def accumulator(x: int, y: int) -> int:
        calls.append((x, y))
        return x + y

    # when
    actual = await Stream([]).reduce(accumulator)

    # then
    assert actual is None
    assert calls == []


@pytest.mark.asyncio
async def test_reduce_no_identity_single_element_returns_it_unchanged() -> None:
    calls = []

    def accumulator(x: int, y: int) -> int:
        calls.append((x, y))
        return x + y

    # when
    actual = await Stream([42]).reduce(accumulator)

    # then
    assert actual == 42
    assert calls == []


@pytest.mark.asyncio
async def test_reduce_no_identity_folds_left_from_first_element() -> None:
    # when
    actual = await Stream([1, 2, 3, 4, 5, 6]).reduce(lambda x, y: x + y)

    # then
    assert actual == 21


@pytest.mark.asyncio
async def test_reduce_no_identity_async_accumulator_is_awaited() -> None:
    async def async_add(x: int, y: int) -> int:
        await asyncio.sleep(0.01)
        return x + y

    # when
    actual = Stream([1, 2, 3, 4, 5, 6]).reduce(async_add)

    # then
    assert not isinstance(actual, int)
    assert await actual == 21


@given(values=st.lists(st.integers(), min_size=1))
@pytest.mark.asyncio
async def test_reduce_no_identity_matches_functools_reduce(values: list[int]) -> None:
    accumulator = lambda x, y: x + y  # noqa: E731

    # when
    actual = await Stream(values).reduce(accumulator)

    # then
    assert actual == functools.reduce(accumulator, values)


@pytest.mark.asyncio
async def test_reduce_with_identity_still_works_unchanged() -> None:
    # when
    actual = await Stream([1, 2, 3, 4, 5, 6]).reduce(0, lambda x, y: x + y)

    # then
    assert actual == 21


@pytest.mark.asyncio
async def test_reduce_no_identity_accumulator_by_keyword() -> None:
    # when
    actual = await Stream([1, 2, 3]).reduce(accumulator=lambda a, b: a + b)

    # then
    assert actual == 6


@pytest.mark.asyncio
async def test_reduce_no_identity_accumulator_by_keyword_empty_stream_returns_none() -> None:
    calls = []

    def accumulator(x: int, y: int) -> int:
        calls.append((x, y))
        return x + y

    # when
    actual = await Stream([]).reduce(accumulator=accumulator)

    # then
    assert actual is None
    assert calls == []


@pytest.mark.asyncio
async def test_reduce_identity_and_accumulator_by_keyword() -> None:
    # when
    actual = await Stream([1, 2, 3]).reduce(identity=10, accumulator=lambda a, b: a + b)

    # then
    assert actual == 16


@pytest.mark.asyncio
async def test_reduce_all_three_by_keyword() -> None:
    # when
    actual = await Stream([1, 2, 3]).reduce(identity=0, accumulator=lambda a, b: a + b, combiner=lambda a, b: a + b)

    # then
    assert actual == 6


@pytest.mark.asyncio
async def test_reduce_all_three_by_keyword_combiner_is_invoked_under_parallel() -> None:
    # given a keyword-spelled three-argument call, on a source large enough
    # to span more than one batch under .parallel()
    calls = 0

    def combiner(a: int, b: int) -> int:
        nonlocal calls
        calls += 1
        return a + b

    # when
    actual = await Stream(list(range(50))).parallel().reduce(identity=0, accumulator=lambda a, b: a + b, combiner=combiner)

    # then
    assert actual == sum(range(50))
    assert calls > 0


@pytest.mark.asyncio
async def test_reduce_falsy_identity_by_keyword_is_not_omitted() -> None:
    # when
    actual = await Stream([1, 2, 3]).reduce(identity=0, accumulator=lambda a, b: a + b)

    # then
    assert actual == 6


@pytest.mark.asyncio
async def test_reduce_combiner_without_identity_is_rejected() -> None:
    with pytest.raises(StreamBuildException):
        await Stream([1, 2, 3]).reduce(accumulator=lambda a, b: a + b, combiner=lambda a, b: a + b)


@pytest.mark.asyncio
async def test_reduce_identity_and_combiner_without_accumulator_is_rejected() -> None:
    # given a call unreachable positionally: identity and combiner supplied,
    # accumulator omitted - identity must not be mistaken for accumulator
    with pytest.raises(StreamBuildException):
        await Stream([1, 2, 3]).reduce(identity=5, combiner=lambda a, b: a + b)


@pytest.mark.asyncio
async def test_reduce_no_accumulator_at_all_is_rejected() -> None:
    with pytest.raises(StreamBuildException):
        await Stream([1, 2, 3]).reduce()
