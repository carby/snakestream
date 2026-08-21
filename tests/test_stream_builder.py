import pytest

from snakestream.collector import to_list
from snakestream.stream_builder import StreamBuilder


def test_add_chains_and_accumulates_in_order() -> None:
    builder: StreamBuilder[int] = StreamBuilder()

    # when
    result = builder.add(1).add(2).add(3)

    # then
    assert result is builder
    assert builder._elements == [1, 2, 3]


def test_accept_accumulates_and_returns_none() -> None:
    builder: StreamBuilder[int] = StreamBuilder()

    # when
    result = builder.accept(1)

    # then
    assert result is None
    assert builder._elements == [1]


@pytest.mark.asyncio
async def test_build_captures_elements_added_before_it() -> None:
    builder: StreamBuilder[int] = StreamBuilder()
    builder.add(1).add(2)

    # when
    stream = builder.build()

    # then
    assert await stream.collect(to_list()) == [1, 2]


@pytest.mark.asyncio
async def test_elements_added_after_build_do_not_leak_into_built_stream() -> None:
    builder: StreamBuilder[int] = StreamBuilder()
    builder.add(1).add(2)
    stream = builder.build()

    # when
    builder.add(3)

    # then
    assert await stream.collect(to_list()) == [1, 2]
