import pytest
from snakestream.collector import to_list

from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_builder_simple() -> None:
    # given
    builder = Stream.builder()
    builder.add(1)
    builder.add(5)
    builder.add(8)

    # when
    stream = builder.build()
    it = await stream.collect(to_list)

    # then
    assert it == [1, 5, 8]


@pytest.mark.asyncio
async def test_builder_empty() -> None:
    # given
    builder = Stream.builder()

    # when
    stream = builder.build()
    it = await stream.collect(to_list)

    # then
    assert it == []
