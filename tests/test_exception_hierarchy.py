import pytest

from snakestream import Stream
from snakestream.exception import IllegalStateException, StreamBuildException, StreamException


@pytest.mark.asyncio
async def test_build_error_is_caught_by_the_base() -> None:
    with pytest.raises(StreamException):
        await Stream.of([1, 2, 3]).collect(lambda c: c)


@pytest.mark.asyncio
async def test_reuse_error_is_caught_by_the_base() -> None:
    stream = Stream.of([1, 2, 3])
    stream.map(lambda x: x)
    with pytest.raises(StreamException):
        stream.map(lambda x: x)


@pytest.mark.asyncio
async def test_existing_leaf_catch_still_works() -> None:
    with pytest.raises(StreamBuildException):
        await Stream.of([1, 2, 3]).collect(lambda c: c)


def test_base_is_not_a_value_error() -> None:
    with pytest.raises(StreamException):
        try:
            raise StreamException("not a ValueError")
        except ValueError:  # pragma: no cover - the point is that this never matches
            pytest.fail("StreamException must not derive from ValueError")


def test_both_leaves_report_the_base_as_an_ancestor() -> None:
    assert issubclass(StreamBuildException, StreamException)
    assert issubclass(IllegalStateException, StreamException)
    assert issubclass(StreamException, Exception)
    assert not issubclass(StreamException, ValueError)
