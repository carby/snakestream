import pickle

import pytest

from snakestream import Stream
from snakestream.collectors import to_list
from snakestream.exception import (
    ComparatorContractException,
    IllegalStateException,
    StreamBuildException,
    StreamException,
)


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
    # PT012 wants one simple statement inside the block, but the try/except IS
    # the demonstration here: the except clause must not match, which is what
    # proves StreamException does not derive from ValueError.
    with pytest.raises(StreamException):  # noqa: PT012
        try:
            raise StreamException("not a ValueError")
        except ValueError:  # pragma: no cover - the point is that this never matches
            pytest.fail("StreamException must not derive from ValueError")


def test_both_leaves_report_the_base_as_an_ancestor() -> None:
    assert issubclass(StreamBuildException, StreamException)
    assert issubclass(IllegalStateException, StreamException)
    assert issubclass(StreamException, Exception)
    assert not issubclass(StreamException, ValueError)


@pytest.mark.asyncio
async def test_bool_comparator_rejection_is_caught_by_stream_build_exception() -> None:
    with pytest.raises(StreamBuildException):
        await Stream.of([3, 1, 2]).sorted(lambda a, b: a > b).collect(to_list())


@pytest.mark.asyncio
async def test_bool_comparator_rejection_is_caught_by_the_library_base() -> None:
    with pytest.raises(StreamException):
        await Stream.of([3, 1, 2]).sorted(lambda a, b: a > b).collect(to_list())


@pytest.mark.asyncio
async def test_bool_comparator_rejection_propagates_uncaught_past_value_error() -> None:
    with pytest.raises(TypeError):  # noqa: PT012
        try:
            await Stream.of([3, 1, 2]).sorted(lambda a, b: a > b).collect(to_list())
        except ValueError:  # pragma: no cover - the point is that this never matches
            pytest.fail("ComparatorContractException must not derive from ValueError")


def test_comparator_contract_exception_reports_all_its_ancestors() -> None:
    assert issubclass(ComparatorContractException, StreamException)
    assert issubclass(ComparatorContractException, StreamBuildException)
    assert issubclass(ComparatorContractException, TypeError)


def test_comparator_contract_exception_renders_the_offending_type() -> None:
    assert str(ComparatorContractException(True)) == "comparator must return an int (negative, zero, or positive), not bool"
    assert str(ComparatorContractException("x")) == "comparator must return an int (negative, zero, or positive), not str"


def test_comparator_contract_exception_survives_a_round_trip() -> None:
    # It holds the offending value in args and renders in __str__ rather than
    # formatting in __init__, because BaseException.__reduce__ replays args
    # through __init__ - a finished message would come back as "not str".
    original = ComparatorContractException(True)
    assert str(pickle.loads(pickle.dumps(original))) == str(original)
