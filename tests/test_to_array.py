import pytest

from snakestream.collectors import to_list
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_to_array_returns_list_of_all_elements() -> None:
    # when
    result = await Stream.of([1, 2, 3]).to_array()

    # then
    assert result == [1, 2, 3]


@pytest.mark.asyncio
async def test_to_array_on_empty_stream_returns_empty_list() -> None:
    # when
    result = await Stream.of([]).to_array()

    # then
    assert result == []


@pytest.mark.asyncio
async def test_to_array_equals_collect_to_list() -> None:
    # given
    chain = lambda: Stream.of([1, 2, 3, 4]).map(lambda x: x * 2).filter(lambda x: x > 2)  # noqa: E731

    # when
    from_to_array = await chain().to_array()
    from_collect = await chain().collect(to_list())

    # then
    assert from_to_array == from_collect == [4, 6, 8]


@pytest.mark.asyncio
async def test_to_array_on_parallel_stream_returns_all_elements() -> None:
    # when
    result = await Stream.of([1, 2, 3, 4]).parallel().to_array()

    # then
    assert sorted(result) == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_to_array_rejects_arguments() -> None:
    # when / then
    with pytest.raises(TypeError):
        await Stream.of([1, 2, 3]).to_array(list)
