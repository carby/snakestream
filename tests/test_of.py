# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name

from collections.abc import AsyncGenerator, Generator
import pytest

from snakestream import Stream
from snakestream.collector import to_generator
from snakestream.collectors import to_list


async def async_generator() -> AsyncGenerator:
    for i in range(1, 6):
        yield i


def generator() -> Generator:
    yield from range(1, 6)


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
    it = Stream([1, 2, 3, 4]).collect(to_generator)
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
        pytest.fail("stream should be exhausted")


@pytest.mark.asyncio
async def test_input_async_generator() -> None:
    # when
    it = Stream(async_generator()).collect(to_generator)

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
        pytest.fail("stream should be exhausted")


@pytest.mark.asyncio
async def test_input_async_iterator() -> None:
    # when
    it = Stream(AsyncIteratorImpl(5)).collect(to_generator)

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
        pytest.fail("stream should be exhausted")


# The scalar-set tests below are written against Stream(...), not Stream.of(...).
# After of() became atomic (design.md, Decision 3), Stream.of(x) agrees with
# Stream(x) for every scalar x by construction - of() no longer spreads
# anything - so a scenario stated against of() would hold whatever
# normalization does and guard nothing.


@pytest.mark.asyncio
async def test_null_input() -> None:
    # when
    it = await Stream(None).collect(to_list())
    assert it == [None]


@pytest.mark.asyncio
async def test_single_var_input() -> None:
    # when
    it = await Stream(1).collect(to_list())
    assert it == [1]


@pytest.mark.asyncio
async def test_single_generator_input() -> None:
    # when
    it = await Stream(generator()).collect(to_list())
    assert it == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_single_empty_stream_no_ref() -> None:
    # when
    actual = await Stream.of().collect(to_list())

    assert actual == []


@pytest.mark.asyncio
async def test_single_empty_list() -> None:
    # when
    actual = await Stream([]).collect(to_list())

    assert actual == []


@pytest.mark.asyncio
async def test_single_empty_dict() -> None:
    # when
    actual = await Stream({}).collect(to_list())

    assert actual == [{}]


def test_kwargs_rejected() -> None:
    # when / then
    with pytest.raises(TypeError):
        Stream.of(a=1)


@pytest.mark.asyncio
async def test_single_str_input() -> None:
    # when
    actual = await Stream("abc").collect(to_list())

    assert actual == ["abc"]


@pytest.mark.asyncio
async def test_single_bytes_input() -> None:
    # when
    actual = await Stream(b"ab").collect(to_list())

    assert actual == [b"ab"]


@pytest.mark.asyncio
async def test_single_populated_dict() -> None:
    # when
    actual = await Stream({"a": 1, "b": 2}).collect(to_list())

    assert actual == [{"a": 1, "b": 2}]


@pytest.mark.asyncio
async def test_populated_dict_and_some_other_literals() -> None:
    # when
    actual = await Stream.of({"a": 1, "b": 2}, {}, [], [1, 2]).collect(to_list())

    assert actual == [{"a": 1, "b": 2}, {}, [], [1, 2]]


@pytest.mark.asyncio
async def test_double_empty_lists() -> None:
    # when
    actual = await Stream.of([], []).collect(to_list())

    assert actual == [[], []]


@pytest.mark.asyncio
async def test_dual_list_stream() -> None:
    actual = await Stream.of([1, 2], [2, 3, 4]).collect(to_list())

    assert actual == [[1, 2], [2, 3, 4]]


@pytest.mark.asyncio
async def test_single_args_stream() -> None:
    actual = await Stream.of(1, 2, 2, 3, 4).collect(to_list())

    assert actual == [1, 2, 2, 3, 4]


@pytest.mark.asyncio
async def test_multiple_args_stream() -> None:
    arr1 = [1, 2, 2]
    arr2 = [3, 4]
    actual = await Stream.of(*arr1, *arr2).collect(to_list())

    assert actual == [1, 2, 2, 3, 4]


@pytest.mark.asyncio
async def test_single_bytearray_input() -> None:
    # given
    source = bytearray(b"ab")

    # when
    actual = await Stream(source).collect(to_list())

    # then: one element, the bytearray itself, not the ints 97 and 98
    assert [source] == actual
    assert isinstance(actual[0], bytearray)


@pytest.mark.asyncio
async def test_single_memoryview_input() -> None:
    # given
    source = memoryview(b"ab")

    # when
    actual = await Stream(source).collect(to_list())

    # then: one element, the memoryview itself, not the ints 97 and 98
    assert len(actual) == 1
    assert actual[0] is source


@pytest.mark.asyncio
async def test_the_three_binary_types_agree() -> None:
    # given: the same two bytes, immutable, mutable, and as a view
    # when
    as_bytes = await Stream(b"ab").collect(to_list())
    as_bytearray = await Stream(bytearray(b"ab")).collect(to_list())
    as_memoryview = await Stream(memoryview(b"ab")).collect(to_list())

    # then: how the buffer is spelled does not change the element count
    assert 1 == len(as_bytes) == len(as_bytearray) == len(as_memoryview)


@pytest.mark.asyncio
async def test_single_list_argument_is_atomic() -> None:
    # when
    actual = await Stream.of([1, 2]).collect(to_list())

    # then: one element, the list itself, not the integers 1 and 2
    assert actual == [[1, 2]]


@pytest.mark.asyncio
async def test_single_generator_argument_is_not_advanced() -> None:
    # given
    g = generator()

    # when
    actual = await Stream.of(g).collect(to_list())

    # then: one element, the generator object itself, never advanced
    assert actual == [g]


@pytest.mark.asyncio
async def test_arity_does_not_change_meaning() -> None:
    # when
    one = await Stream.of([1, 2]).collect(to_list())
    two = await Stream.of([1, 2], [3, 4]).collect(to_list())

    # then: adding an argument adds an element, changes nothing already present
    assert one == [[1, 2]]
    assert two == [[1, 2], [3, 4]]
