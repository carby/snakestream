import pytest

from snakestream.collectors import to_list
from snakestream.exception import IllegalStateException
from snakestream.stream import Stream


def _fresh_stream() -> Stream:
    return Stream.of([1, 2, 3])


INTERMEDIATE_OPS = [
    ("filter", lambda s: s.filter(lambda x: True)),
    ("map", lambda s: s.map(lambda x: x)),
    ("flat_map", lambda s: s.flat_map(Stream.of)),
    ("sorted", lambda s: s.sorted()),
    ("distinct", lambda s: s.distinct()),
    ("peek", lambda s: s.peek(lambda x: None)),
    ("limit", lambda s: s.limit(2)),
    ("skip", lambda s: s.skip(1)),
    ("unordered", lambda s: s.unordered()),
]

TERMINAL_OPS = [
    ("collect", lambda s: s.collect(to_list())),
    ("reduce_no_identity", lambda s: s.reduce(lambda a, b: a)),
    ("reduce_identity", lambda s: s.reduce(0, lambda a, b: a + b)),
    ("for_each", lambda s: s.for_each(lambda x: None)),
    ("for_each_ordered", lambda s: s.for_each_ordered(lambda x: None)),
    ("find_any", lambda s: s.find_any()),
    ("find_first", lambda s: s.find_first()),
    ("max", lambda s: s.max(lambda a, b: (a > b) - (a < b))),
    ("min", lambda s: s.min(lambda a, b: (a > b) - (a < b))),
    ("all_match", lambda s: s.all_match(lambda x: True)),
    ("any_match", lambda s: s.any_match(lambda x: True)),
    ("none_match", lambda s: s.none_match(lambda x: False)),
    ("count", lambda s: s.count()),
    ("to_array", lambda s: s.to_array()),
]


@pytest.mark.parametrize(("name", "op"), INTERMEDIATE_OPS, ids=[n for n, _ in INTERMEDIATE_OPS])
def test_intermediate_op_returns_new_instance(name, op) -> None:
    s = _fresh_stream()
    s2 = op(s)
    assert s2 is not s


@pytest.mark.parametrize(("name", "op"), INTERMEDIATE_OPS, ids=[n for n, _ in INTERMEDIATE_OPS])
def test_intermediate_op_twice_on_same_reference_raises(name, op) -> None:
    s = _fresh_stream()
    op(s)

    with pytest.raises(IllegalStateException):
        op(s)


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "op"), TERMINAL_OPS, ids=[n for n, _ in TERMINAL_OPS])
async def test_terminal_op_on_already_extended_reference_raises(name, op) -> None:
    s = _fresh_stream()
    s.map(lambda x: x)  # extends s into a new instance, invalidating s

    with pytest.raises(IllegalStateException):
        await op(s)


def test_iterator_on_already_extended_reference_raises() -> None:
    s = _fresh_stream()
    s.map(lambda x: x)

    with pytest.raises(IllegalStateException):
        s.iterator()


@pytest.mark.asyncio
async def test_parallel_invalidates_receiver() -> None:
    s = _fresh_stream()
    p = s.parallel()

    assert p is not s
    with pytest.raises(IllegalStateException):
        s.map(lambda x: x)
    with pytest.raises(IllegalStateException):
        await s.collect(to_list())


@pytest.mark.asyncio
async def test_sequential_invalidates_receiver() -> None:
    s = _fresh_stream().parallel()
    seq = s.sequential()

    assert seq is not s
    with pytest.raises(IllegalStateException):
        s.map(lambda x: x)
    with pytest.raises(IllegalStateException):
        await s.collect(to_list())


@pytest.mark.asyncio
async def test_derived_instance_is_fully_usable() -> None:
    s = _fresh_stream()
    s2 = s.map(lambda x: x * 2)
    s3 = s2.filter(lambda x: x > 2)

    result = await s3.collect(to_list())

    assert result == [4, 6]


@pytest.mark.asyncio
async def test_repeat_terminal_call_on_unextended_reference_still_allowed() -> None:
    # given: a reference that has never been used to build a further
    # instance - only terminally consumed, per the existing
    # pipeline-composition / fix-stream-rerun-state contract this change
    # must not regress
    s = _fresh_stream().distinct()

    first = await s.collect(to_list())
    second = await s.collect(to_list())

    assert first == [1, 2, 3]
    assert second == []


def test_close_succeeds_after_receiver_invalidated(mocker) -> None:
    handler = mocker.Mock()
    s = _fresh_stream()
    s.on_close(handler)
    s.map(lambda x: x)  # invalidates s for pipeline purposes

    s.close()

    handler.assert_called_once()


def test_on_close_on_already_extended_reference_still_registers(mocker) -> None:
    handler = mocker.Mock()
    s = _fresh_stream()
    s.map(lambda x: x)  # invalidates s for pipeline purposes

    s.on_close(handler)
    s.close()

    handler.assert_called_once()
