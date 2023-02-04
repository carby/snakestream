import pytest

from snakestream import stream_of
from snakestream.collector import to_generator


@pytest.mark.asyncio
async def test_mixed_chain(int_2_letter) -> None:
    # when
    it = stream_of([1, 2, 3, 4, 5, 6]) \
        .filter(lambda x: 3 < x < 6) \
        .map(lambda x: int_2_letter[x]) \
        .collect(to_generator)

    # then
    assert await it.__anext__() == 'd'
    assert await it.__anext__() == 'e'
    try:
        await it.__anext__()
    except StopAsyncIteration:
        pass
    else:
        assert False
