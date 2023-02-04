import pytest
import asyncio

from snakestream import stream_of


coords = [
    {'x': 1, 'y': 5},
    {'x': 2, 'y': 6},
    {'x': 3, 'y': 7},
]


@pytest.mark.asyncio
async def test_for_each() -> None:
    def incr_y(c) -> None:
        c['y'] = 1

    await stream_of(coords) \
        .for_each(incr_y)

    assert coords[0]['y'] == 1
    assert coords[1]['y'] == 1
    assert coords[2]['y'] == 1


@pytest.mark.asyncio
async def test_for_each_async() -> None:
    async def async_incr_y(c) -> None:
        await asyncio.sleep(0.01)
        c['y'] = 1

    await stream_of(coords) \
        .for_each(async_incr_y)

    assert coords[0]['y'] == 1
    assert coords[1]['y'] == 1
    assert coords[2]['y'] == 1
