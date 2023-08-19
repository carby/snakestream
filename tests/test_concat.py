
import pytest

from snakestream import stream_of
from snakestream.collector import to_generator
from snakestream.core import Stream


@pytest.mark.asyncio
async def test_to_generator() -> None:
    # when
    a = stream_of([1, 2, 3, 4])
    b = stream_of([5, 6, 7])

    c = Stream.concat(a, b) \
        .collect(to_generator)

    # then
    assert await c.__anext__() == 1
    assert await c.__anext__() == 2
    assert await c.__anext__() == 3
    assert await c.__anext__() == 4
    assert await c.__anext__() == 5
    assert await c.__anext__() == 6
    assert await c.__anext__() == 7

    with pytest.raises(StopAsyncIteration):
        await c.__anext__()
