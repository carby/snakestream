# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name

from typing import AsyncGenerator, Generator
import pytest

from snakestream import Stream
from snakestream.collector import to_generator, to_list


async def async_generator() -> AsyncGenerator:
    for i in range(1, 6):
        yield i


def generator() -> Generator:
    for i in range(1, 6):
        yield i


class AsyncIteratorImpl:
    def __init__(self, end_range):
        self.end = end_range
        self.start = -1

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.start < self.end - 1:
            self.start += 1
            return self.start
        raise StopAsyncIteration


@pytest.mark.asyncio
async def test_input_list() -> None:
    # when
    it = Stream.of([1, 2, 3, 4]) \
        .collect(to_generator)
    # then
    assert await it.__anext__() == 1
    assert await it.__anext__() == 2
    assert await it.__anext__() == 3
    assert await it.__anext__() == 4
    try:
        await it.__anext__()
    except StopAsyncIteration:
        pass
    else:
        assert False


@pytest.mark.asyncio
async def test_input_async_generator() -> None:
    # when
    it = Stream.of(async_generator()) \
        .collect(to_generator)

    # then
    assert await it.__anext__() == 1
    assert await it.__anext__() == 2
    assert await it.__anext__() == 3
    assert await it.__anext__() == 4
    assert await it.__anext__() == 5
    try:
        await it.__anext__()
    except StopAsyncIteration:
        pass
    else:
        assert False


@pytest.mark.asyncio
async def test_input_async_iterator() -> None:
    # when
    it = Stream.of(AsyncIteratorImpl(5)) \
        .collect(to_generator)

    # then
    assert await it.__anext__() == 0
    assert await it.__anext__() == 1
    assert await it.__anext__() == 2
    assert await it.__anext__() == 3
    assert await it.__anext__() == 4
    try:
        await it.__anext__()
    except StopAsyncIteration:
        pass
    else:
        assert False


@pytest.mark.asyncio
async def test_null_input() -> None:
    # when
    it = await Stream.of(None) \
        .collect(to_list)
    assert [None] == it


@pytest.mark.asyncio
async def test_single_var_input() -> None:
    # when
    it = await Stream.of(1) \
        .collect(to_list)
    assert [1] == it


@pytest.mark.asyncio
async def test_single_generator_input() -> None:
    # when
    it = await Stream.of(generator()) \
        .collect(to_list)
    assert [1, 2, 3, 4, 5] == it


@pytest.mark.asyncio
async def test_single_empty_stream_no_ref() -> None:
    # when
    actual = await Stream.of() \
        .collect(to_list)

    assert [] == actual


@pytest.mark.asyncio
async def test_single_empty_list() -> None:
    # when
    actual = await Stream.of([]) \
        .collect(to_list)

    assert [] == actual


@pytest.mark.asyncio
async def test_single_empty_dict() -> None:
    # when
    actual = await Stream.of({}) \
        .collect(to_list)

    assert [{}] == actual


@pytest.mark.asyncio
async def test_single_kw_arg() -> None:
    # when
    actual = await Stream.of(a=1) \
        .collect(to_list)

    assert [('a', 1)] == actual


@pytest.mark.asyncio
async def test_kw_and_regular_arg() -> None:
    # when
    actual = await Stream.of(3, a=1) \
        .collect(to_list)

    assert [3, ('a', 1)] == actual


@pytest.mark.asyncio
async def test_multiple_kw() -> None:
    # when
    actual = await Stream.of(a=1, b=2) \
        .collect(to_list)

    assert [('a', 1), ('b', 2)] == actual


@pytest.mark.asyncio
async def test_multiple_kw_mixed() -> None:
    # when
    actual = await Stream.of(3, a=1, b=2) \
        .collect(to_list)

    assert [3, ('a', 1), ('b', 2)] == actual


@pytest.mark.asyncio
async def test_single_populated_dict() -> None:
    # when
    actual = await Stream.of({'a': 1, 'b': 2}) \
        .collect(to_list)

    assert [{'a': 1, 'b': 2}] == actual


@pytest.mark.asyncio
async def test_populated_dict_and_some_other_literals() -> None:
    # when
    actual = await Stream.of({'a': 1, 'b': 2}, {}, [], [1, 2]) \
        .collect(to_list)

    assert [{'a': 1, 'b': 2}, {}, [], [1, 2]] == actual


@pytest.mark.asyncio
async def test_double_empty_lists() -> None:
    # when
    actual = await Stream.of([], []) \
        .collect(to_list)

    assert [[], []] == actual


@pytest.mark.asyncio
async def test_dual_list_stream() -> None:
    actual = await Stream.of([1, 2], [2, 3, 4]) \
        .collect(to_list)

    assert [[1, 2], [2, 3, 4]] == actual


@pytest.mark.asyncio
async def test_single_args_stream() -> None:
    actual = await Stream.of(1, 2, 2, 3, 4) \
        .collect(to_list)

    assert [1, 2, 2, 3, 4] == actual


@pytest.mark.asyncio
async def test_multiple_args_stream() -> None:
    arr1 = [1, 2, 2]
    arr2 = [3, 4]
    actual = await Stream.of(*arr1, *arr2) \
        .collect(to_list)

    assert [1, 2, 2, 3, 4] == actual
