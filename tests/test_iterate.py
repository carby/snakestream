
import pytest

from snakestream.collector import to_generator
from snakestream.stream import Stream


@pytest.mark.asyncio
async def test_iterate_simple() -> None:
    # when
    it = Stream.iterate(0, lambda n: n + 1) \
        .collect(to_generator)

    # then
    assert await it.__anext__() == 0
    assert await it.__anext__() == 1
    assert await it.__anext__() == 2
    assert await it.__anext__() == 3
    assert await it.__anext__() == 4
    assert await it.__anext__() == 5


@pytest.mark.asyncio
async def test_iterate_fib() -> None:
    # when
    it = Stream.iterate((0, 1), lambda n: (n[1], n[0] + n[1])) \
        .collect(to_generator)

    # then
    assert (await it.__anext__())[0] == 0
    assert (await it.__anext__())[0] == 1
    assert (await it.__anext__())[0] == 1
    assert (await it.__anext__())[0] == 2
    assert (await it.__anext__())[0] == 3
    assert (await it.__anext__())[0] == 5
    assert (await it.__anext__())[0] == 8
    assert (await it.__anext__())[0] == 13
    assert (await it.__anext__())[0] == 21
    assert (await it.__anext__())[0] == 34
    assert (await it.__anext__())[0] == 55
