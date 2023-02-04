import pytest

from snakestream import stream_of, Stream
from snakestream.collector import to_list


@pytest.mark.asyncio
async def test_empty_stream() -> None:
    # when
    expected = stream_of([])
    actual = Stream.empty()

    assert await expected.collect(to_list) == await actual.collect(to_list)
