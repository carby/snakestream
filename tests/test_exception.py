import pytest

from snakestream import Stream
from snakestream.collectors import to_list


@pytest.mark.asyncio
async def test_map_exception_propagates_sequential() -> None:
    def boom(x):
        if x == 3:
            raise ValueError("boom")
        return x

    with pytest.raises(ValueError):
        await Stream.of([1, 2, 3, 4]).map(boom).collect(to_list())


@pytest.mark.asyncio
async def test_map_exception_propagates_parallel() -> None:
    def boom(x):
        if x == 3:
            raise ValueError("boom")
        return x

    with pytest.raises(ValueError):
        await Stream.of([1, 2, 3, 4]).parallel().map(boom).collect(to_list())


@pytest.mark.asyncio
async def test_filter_exception_propagates_sequential() -> None:
    def boom(x):
        if x == 3:
            raise ValueError("boom")
        return True

    with pytest.raises(ValueError):
        await Stream.of([1, 2, 3, 4]).filter(boom).collect(to_list())
