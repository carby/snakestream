"""Covers the stream-execution-model capability: execution mode as a value
rather than a type, the executor a terminal uses, and the mode switches that
carry a chain rather than freezing it."""

import asyncio
import time

import pytest

from snakestream import Stream
from snakestream.collectors import to_list
from snakestream.exception import IllegalStateException
from snakestream.execution import RACING, SEQUENTIAL


# --- execution mode is a value ---------------------------------------------


@pytest.mark.asyncio
async def test_a_sequentially_built_stream_reports_sequential() -> None:
    assert Stream.of([1, 2, 3]).is_parallel() is False


@pytest.mark.asyncio
async def test_a_parallel_stream_reports_parallel() -> None:
    assert Stream.of([1, 2, 3]).parallel().is_parallel() is True


@pytest.mark.asyncio
async def test_intermediate_operations_carry_the_executor_forward() -> None:
    # when
    s = Stream.of([1, 2, 3]).parallel().map(lambda x: x).filter(lambda x: True)
    # then
    assert s.is_parallel() is True


@pytest.mark.asyncio
async def test_a_user_subclass_survives_a_mode_switch() -> None:
    # given: the documented use case of subclassing Stream to wrap a resource
    class MyStream(Stream):
        def __init__(self, source, close_handlers=None) -> None:
            super().__init__(source, close_handlers)
            self.resource = "db-handle"

    # when
    par = MyStream([1, 2, 3]).parallel()
    seq = par.sequential()

    # then: mode switches used to be the only ops in the library that dropped
    # subclass identity, because they constructed a fixed class
    assert isinstance(par, MyStream)
    assert isinstance(seq, MyStream)
    assert seq.resource == "db-handle"


# --- a mode switch carries the chain, it does not compose it ---------------


@pytest.mark.asyncio
async def test_a_mode_switch_does_not_compose_the_queued_chain() -> None:
    # given: an op queued before the switch
    seen = []

    # when
    it = await Stream.of([1, 2, 3]).peek(seen.append).sequential().collect(to_list())

    # then: the op still ran, and the switch left it queued rather than
    # freezing it into a composed source
    assert sorted(it) == [1, 2, 3]
    assert sorted(seen) == [1, 2, 3]


@pytest.mark.asyncio
async def test_a_mode_switch_returns_a_distinct_object_and_consumes_the_receiver() -> None:
    # given
    s = Stream.of([1, 2, 3])

    # when
    p = s.parallel()

    # then
    assert p is not s
    with pytest.raises(IllegalStateException):
        await s.collect(to_list())


@pytest.mark.asyncio
async def test_a_stateful_op_declared_before_parallel_stays_globally_correct() -> None:
    # when: distinct() is declared before the switch, so it now runs across
    # racing branches rather than in a frozen sequential pass
    it = await Stream.of([1, 2, 3] * 10).distinct().parallel().collect(to_list())
    # then
    assert sorted(it) == [1, 2, 3]


# --- which executor a terminal uses ----------------------------------------


async def _delayed(x: int) -> int:
    # later elements finish sooner, so arrival order != encounter order
    await asyncio.sleep((5 - x) * 0.02)
    return x


@pytest.mark.asyncio
async def test_an_ordinary_terminal_follows_the_streams_executor() -> None:
    # given a mapper slow enough for racing to show in wall clock
    async def slow(x: int) -> int:
        await asyncio.sleep(0.1)
        return x

    # when
    started = time.time()
    await Stream.of(list(range(8))).parallel().map(slow).count()
    elapsed = time.time() - started

    # then count() raced, rather than forcing an ordered drive
    assert elapsed < 0.35


@pytest.mark.asyncio
async def test_for_each_ordered_ignores_the_streams_executor() -> None:
    # given
    seen: list[int] = []

    # when
    await Stream.of([1, 2, 3, 4]).parallel().map(_delayed).for_each_ordered(seen.append)

    # then
    assert seen == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_find_first_on_an_ordered_parallel_stream_ignores_the_executor() -> None:
    # when
    it = await Stream.of([1, 2, 3, 4]).parallel().map(_delayed).find_first()
    # then: the true first element, not the first to arrive
    assert it == 1


@pytest.mark.asyncio
async def test_find_first_holds_when_the_op_is_declared_before_parallel() -> None:
    # when: the map now runs under the racing executor for ordinary terminals,
    # but find_first drives under SEQUENTIAL regardless
    it = await Stream.of([1, 2, 3, 4]).map(_delayed).parallel().find_first()
    # then
    assert it == 1


@pytest.mark.asyncio
async def test_find_first_on_an_unordered_stream_does_not_force_sequential() -> None:
    # when
    it = await Stream.of([1, 2, 3, 4]).parallel().unordered().map(_delayed).find_first()
    # then: behaves as find_any(), so any element is admissible
    assert it in [1, 2, 3, 4]


# --- the executor protocol -------------------------------------------------


@pytest.mark.asyncio
async def test_both_executors_produce_the_same_elements() -> None:
    # when
    seq = await Stream.of(list(range(20))).map(lambda x: x * 2).collect(to_list())
    par = await Stream.of(list(range(20))).parallel().map(lambda x: x * 2).collect(to_list())
    # then: same elements, subject only to each mode's ordering guarantee
    assert sorted(par) == seq


@pytest.mark.asyncio
async def test_the_fused_override_is_indistinguishable_from_the_generic_form() -> None:
    from snakestream.terminals import _CountSink

    async def source():
        for i in range(10):
            yield i

    async def other():
        for i in range(10):
            yield i

    # when: the same chain and terminal, driven both ways
    fused = await SEQUENTIAL.value([], source(), _CountSink())
    generic = await super(type(SEQUENTIAL), SEQUENTIAL).value([], other(), _CountSink())

    # then
    assert fused == generic == 10


@pytest.mark.asyncio
async def test_racing_uses_the_generic_value_unchanged() -> None:
    # then: Racing does not override value() — each branch owns its own sink
    # chain, so there is no single chain to fuse a terminal onto
    assert type(RACING).value is type(SEQUENTIAL).__mro__[1].value
    assert type(SEQUENTIAL).value is not type(SEQUENTIAL).__mro__[1].value


# --- source acceptance does not depend on execution mode --------------------


class _BareAsyncIter:
    """__aiter__ returning self, __anext__, and deliberately no aclose() —
    the shape an `async def` generator function does NOT produce."""

    def __init__(self, n: int) -> None:
        self._it = iter(range(n))

    def __aiter__(self) -> "_BareAsyncIter":
        return self

    async def __anext__(self) -> int:
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration from None


class _SeparateIterAsyncIterable:
    """__aiter__ handing back a fresh iterator rather than self, so a consumer
    that calls __anext__ on the object itself, or that calls __aiter__ once per
    branch, gets it wrong."""

    def __init__(self, n: int) -> None:
        self._n = n

    def __aiter__(self):
        async def gen():
            for i in range(self._n):
                yield i

        return gen()


@pytest.mark.asyncio
async def test_racing_over_an_async_iterator_with_no_aclose() -> None:
    # when
    sequential = await Stream(_BareAsyncIter(5)).collect(to_list())
    racing = await Stream(_BareAsyncIter(5)).parallel().collect(to_list())

    # then: no AttributeError, and the same elements as a multiset
    assert sorted(racing) == sorted(sequential) == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_racing_over_a_source_whose_aiter_returns_a_separate_iterator() -> None:
    # when
    racing = await Stream(_SeparateIterAsyncIterable(5)).parallel().collect(to_list())

    # then: the exact multiset, not merely the absence of an AttributeError.
    # aiter() called once per branch instead of once per consumption would
    # give every branch its own iterator and yield each element PROCESSES
    # times over, which an existence-only assertion would happily pass.
    assert sorted(racing) == [0, 1, 2, 3, 4]
    assert len(racing) == 5


@pytest.mark.asyncio
async def test_a_closeable_source_is_still_closed_under_racing() -> None:
    # given
    closed = False

    async def source():
        nonlocal closed
        try:
            for i in range(5):
                yield i
        finally:
            closed = True

    # when
    racing = await Stream(source()).parallel().collect(to_list())

    # then
    assert sorted(racing) == [0, 1, 2, 3, 4]
    assert closed is True


class _BareSyncIter:
    """__next__ only, no __iter__ — the sync counterpart, spread by source
    normalization rather than passed through."""

    def __init__(self, n: int) -> None:
        self._it = iter(range(n))

    def __next__(self) -> int:
        return next(self._it)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "make_source",
    [
        lambda: [0, 1, 2, 3, 4],
        lambda: _BareSyncIter(5),
        lambda: 7,
        lambda: bytearray(b"ab"),
    ],
    ids=["list", "bare-sync-iterator", "scalar", "bytearray-scalar"],
)
async def test_sync_and_scalar_sources_race_identically(make_source) -> None:
    # when
    sequential = await Stream(make_source()).collect(to_list())
    racing = await Stream(make_source()).parallel().collect(to_list())

    # then: same multiset; racing makes no promise about order
    assert len(racing) == len(sequential)
    assert all(element in sequential for element in racing)
