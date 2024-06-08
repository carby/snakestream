
import pytest

from snakestream.collector import to_generator
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_concat_simple() -> None:
    # when
    a = Stream.of([1, 2, 3, 4])
    b = Stream.of([5, 6, 7])

    generator = (await Stream.concat(a, b)) \
        .collect(to_generator)

    # then
    assert await generator.__anext__() == 1
    assert await generator.__anext__() == 2
    assert await generator.__anext__() == 3
    assert await generator.__anext__() == 4
    assert await generator.__anext__() == 5
    assert await generator.__anext__() == 6
    assert await generator.__anext__() == 7

    with pytest.raises(StopAsyncIteration):
        await generator.__anext__()


@pytest.mark.asyncio
async def test_concat_with_intermediaries() -> None:
    # when
    a = Stream.of([1, 2, 3, 4]) \
        .filter(lambda x: x < 3)
    b = Stream.of([5, 6, 7, 7]) \
        .distinct()

    generator = (await Stream.concat(a, b)) \
        .collect(to_generator)

    # then
    assert await generator.__anext__() == 1
    assert await generator.__anext__() == 2
    assert await generator.__anext__() == 5
    assert await generator.__anext__() == 6
    assert await generator.__anext__() == 7

    with pytest.raises(StopAsyncIteration):
        await generator.__anext__()
