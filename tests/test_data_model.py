"""Which of Python's data-model protocols a Stream satisfies, and which it refuses.

The split is decided by the library being async-first. Every terminal is a
coroutine, so a protocol demanding a value synchronously cannot be satisfied at
all; what is implemented is the part that does not - the async iteration hook,
the two lifecycle protocols, and one operator. Two of the refusals matter as
much as the implementations: __bool__ raises rather than leaving object's
always-True default in place, and __getitem__ stays absent because defining it
would switch on Python's legacy iteration protocol behind everyone's back.
"""

import asyncio
import copy

import pytest

from snakestream import Stream
from snakestream.collectors import to_list
from snakestream.exception import IllegalStateException


# The refused protocols have to be exercised through helpers: a bare `1 in s`
# or `not s` in a test body is a pointless-expression the linter rejects, and
# pytest.raises() wants one simple statement.


def _takes_if_branch(stream: Stream) -> bool:
    # SIM103 wants `return bool(stream)`, which would defeat the helper: the
    # point is to exercise the *implicit* truth test an `if` performs, where
    # test_bool_on_a_stream_raises already covers the explicit bool() call.
    if stream:  # noqa: SIM103
        return True
    return False


def _negated(stream: Stream) -> bool:
    return not stream


def _contains(stream: Stream, element: int) -> bool:
    return element in stream  # type: ignore[operator]


def _subscript(stream: Stream, key: object) -> object:
    return stream[key]  # type: ignore[index]


def _added(stream: Stream, other: object) -> Stream:
    return stream + other  # type: ignore[operator]


# --- __aiter__: parity with Java's iterable stream -------------------------


@pytest.mark.asyncio
async def test_async_for_yields_what_iterator_yields() -> None:
    direct = [x async for x in Stream.of([1, 2, 3, 4]).map(lambda x: x * 2).filter(lambda x: x > 2)]
    via = [x async for x in Stream.of([1, 2, 3, 4]).map(lambda x: x * 2).filter(lambda x: x > 2).iterator()]
    assert direct == via == [4, 6, 8]


@pytest.mark.asyncio
async def test_aiter_pulls_nothing_until_driven() -> None:
    seen: list[int] = []
    it = Stream.of([1, 2, 3]).peek(seen.append).__aiter__()
    assert seen == []
    assert await it.__anext__() == 1
    assert seen == [1]


@pytest.mark.asyncio
async def test_async_for_over_an_ordered_racing_stream_is_in_encounter_order() -> None:
    # the early elements are the expensive ones, so under a plain race the
    # cheap tail overtakes the slow head and the assertion has something to
    # catch. Without that shape it would pass for the wrong reason.
    source = list(range(20))

    async def slow_head(n: int) -> int:
        await asyncio.sleep(0.05 if n < 5 else 0.001)
        return n

    assert [x async for x in Stream.of(source).parallel().map(slow_head)] == source


@pytest.mark.asyncio
async def test_async_for_over_an_extended_reference_raises() -> None:
    s = Stream.of([1, 2, 3])
    s.map(lambda x: x)
    with pytest.raises(IllegalStateException):
        [x async for x in s]


# --- with: parity with Java's AutoCloseable stream -------------------------


def test_enter_returns_the_stream_itself() -> None:
    s = Stream.of([1, 2, 3])
    with s as entered:
        assert entered is s


def test_a_close_handler_runs_on_block_exit() -> None:
    calls: list[str] = []
    with Stream.of([1, 2, 3]).on_close(lambda: calls.append("closed")):
        assert calls == []
    assert calls == ["closed"]


def test_handlers_still_run_when_the_block_raises() -> None:
    calls: list[str] = []
    with (
        pytest.raises(ValueError, match="boom"),
        Stream.of([1, 2, 3]).on_close(lambda: calls.append("closed")),
    ):
        raise ValueError("boom")
    # closed, and the exception was not suppressed
    assert calls == ["closed"]


def test_every_handler_runs_in_registration_order() -> None:
    calls: list[str] = []
    s = Stream.of([1, 2, 3]).on_close(lambda: calls.append("h1")).on_close(lambda: calls.append("h2"))
    with s:
        pass
    assert calls == ["h1", "h2"]


def test_entering_an_extended_reference_does_not_raise() -> None:
    # on_close()/close() are exempt from invalidation per pipeline-immutability,
    # and __exit__ delegates to close(), so entering inherits the exemption
    calls: list[str] = []
    s = Stream.of([1, 2, 3]).on_close(lambda: calls.append("closed"))
    s.map(lambda x: x)
    with s:
        pass
    assert calls == ["closed"]


@pytest.mark.asyncio
async def test_the_stream_is_usable_inside_the_block() -> None:
    with Stream.of([1, 2, 3]) as s:
        assert await s.map(lambda x: x * 2).collect(to_list()) == [2, 4, 6]


# --- __repr__ ---------------------------------------------------------------


def test_repr_names_the_type_the_chain_and_the_mode() -> None:
    r = repr(Stream.of([1, 2, 3]).map(lambda x: x).filter(lambda x: True).parallel())
    assert r == "<Stream [map, filter] parallel>"


def test_repr_of_a_bare_sequential_stream() -> None:
    assert repr(Stream.of([1, 2, 3])) == "<Stream [] sequential>"


def test_repr_names_a_subclass() -> None:
    class MyStream(Stream):
        pass

    assert repr(MyStream([1, 2])) == "<MyStream [] sequential>"


def test_repr_shows_the_stage_concat_seeds() -> None:
    # concat() introduces an unordered stage on the caller's behalf when either
    # operand is unordered. It is a truthful description of the pipeline, so it
    # should show rather than be hidden.
    assert repr(Stream.concat(Stream.of([1]).unordered(), Stream.of([2]))) == "<Stream [unordered] sequential>"


def test_repr_pulls_nothing() -> None:
    seen: list[int] = []
    repr(Stream.of([1, 2, 3]).peek(seen.append))
    assert seen == []


def test_repr_of_an_extended_stream_does_not_raise() -> None:
    s = Stream.of([1, 2, 3])
    s.map(lambda x: x)
    assert repr(s).startswith("<Stream ")


# --- __bool__: the one refusal that closes a hole ---------------------------


def test_bool_on_a_stream_raises() -> None:
    with pytest.raises(TypeError):
        bool(Stream.of([1, 2, 3]))


def test_an_implicit_truth_test_raises() -> None:
    with pytest.raises(TypeError):
        _takes_if_branch(Stream.of([1, 2, 3]))
    with pytest.raises(TypeError):
        _negated(Stream.of([1, 2, 3]))


def test_an_empty_stream_is_not_silently_truthy() -> None:
    # what this requirement is for: object.__bool__ made every Stream truthy,
    # an empty one included, so `if stream:` answered wrong every time and
    # nothing said so
    with pytest.raises(TypeError):
        bool(Stream.empty())


def test_the_bool_message_names_an_async_alternative() -> None:
    # a TypeError that only says no leaves the caller no better off than the
    # wrong True did
    with pytest.raises(TypeError) as excinfo:
        bool(Stream.of([1]))
    message = str(excinfo.value)
    assert "count()" in message
    assert "any_match" in message


# --- __add__: the deliberate expansion --------------------------------------


@pytest.mark.asyncio
async def test_adding_two_streams_concatenates_them() -> None:
    assert await (Stream.of([1, 2, 3]) + Stream.of([4, 5])).collect(to_list()) == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_the_operator_matches_concat_exactly() -> None:
    added = Stream.of([1, 2]).parallel() + Stream.of([3]).unordered()
    concatenated = Stream.concat(Stream.of([1, 2]).parallel(), Stream.of([3]).unordered())
    assert added.is_parallel() == concatenated.is_parallel() is True
    assert added._is_ordered() == concatenated._is_ordered() is False
    assert type(added) is type(concatenated) is Stream


def test_the_operator_carries_both_operands_close_handlers() -> None:
    calls: list[str] = []
    a = Stream.of([1, 2]).on_close(lambda: calls.append("a"))
    b = Stream.of([3]).on_close(lambda: calls.append("b"))
    (a + b).close()
    assert calls == ["a", "b"]


@pytest.mark.asyncio
async def test_the_operator_invalidates_both_operands() -> None:
    a, b = Stream.of([1, 2]), Stream.of([3])
    a + b
    with pytest.raises(IllegalStateException):
        await a.collect(to_list())
    with pytest.raises(IllegalStateException):
        b.map(lambda x: x)


@pytest.mark.asyncio
async def test_the_operator_chains() -> None:
    # why no n-ary concat() is needed
    total = Stream.of([1, 2]) + Stream.of([3]) + Stream.of([4, 5])
    assert await total.collect(to_list()) == [1, 2, 3, 4, 5]


def test_adding_a_non_stream_raises_without_coercing() -> None:
    for other in ([1, 2], "xs", 3, None):
        with pytest.raises(TypeError):
            _added(Stream.of([1]), other)


# --- the refusals -----------------------------------------------------------


def test_synchronous_iteration_is_refused() -> None:
    seen: list[int] = []
    s = Stream.of([1, 2, 3]).peek(seen.append)
    with pytest.raises(TypeError):
        list(s)
    assert seen == []


def test_length_is_refused() -> None:
    with pytest.raises(TypeError):
        len(Stream.of([1, 2, 3]))  # type: ignore[arg-type]


def test_membership_testing_is_refused() -> None:
    seen: list[int] = []
    s = Stream.of([1, 2, 3]).peek(seen.append)
    with pytest.raises(TypeError):
        _contains(s, 1)
    assert seen == []


def test_subscripting_is_refused() -> None:
    # excluded on a mechanical hazard rather than on taste: Python synthesizes
    # an iterator from __getitem__ when __iter__ is absent, so defining it would
    # make `for x in stream` call stream[0], receive a Stream, and loop forever.
    # skip()/limit() is what Java offers and is clearer than s[10:20] anyway.
    s = Stream.of([1, 2, 3])
    with pytest.raises(TypeError):
        _subscript(s, 0)
    with pytest.raises(TypeError):
        _subscript(s, slice(1, 3))


def test_reversal_is_refused() -> None:
    with pytest.raises(TypeError):
        reversed(Stream.of([1, 2, 3]))  # type: ignore[call-overload]


def test_equality_remains_identity() -> None:
    seen_a: list[int] = []
    seen_b: list[int] = []
    a = Stream.of([1, 2, 3]).peek(seen_a.append)
    b = Stream.of([1, 2, 3]).peek(seen_b.append)
    same_stream_as_a = a
    assert (a == b) is False
    assert (a == same_stream_as_a) is True
    assert seen_a == []
    assert seen_b == []


def test_stream_defines_none_of_the_refused_protocols() -> None:
    # the refusals are specified rather than merely absent, so the difference
    # between "we decided" and "nobody thought about it" is visible
    for name in ("__len__", "__iter__", "__contains__", "__getitem__", "__reversed__", "__eq__"):
        assert name not in vars(Stream), name


# --- copy.copy is derivation's mechanism, so it stays honest here -----------


def test_copying_a_stream_does_not_go_through_the_data_model_hooks() -> None:
    # _derive() copies rather than constructs; nothing added above should have
    # changed what a copy is
    s = Stream.of([1, 2, 3]).map(lambda x: x)
    clone = copy.copy(s)
    assert clone._source is s._source
    assert clone._close_handlers is s._close_handlers
