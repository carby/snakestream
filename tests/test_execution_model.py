"""Covers the stream-execution-model capability: execution mode as a value
rather than a type, the executor a terminal uses, and the mode switches that
carry a chain rather than freezing it."""

import asyncio
import time

import pytest

from snakestream import Stream
from snakestream.collectors import to_list
from snakestream.exception import IllegalStateException
from snakestream.execution import FORK_JOIN, SEQUENTIAL
from snakestream.ordering import OrderDemand


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
            self.resource = object()

    # when
    original = MyStream([1, 2, 3])
    acquired = original.resource
    par = original.parallel()
    seq = par.sequential()

    # then: mode switches used to be the only ops in the library that dropped
    # subclass identity, because they constructed a fixed class
    assert isinstance(par, MyStream)
    assert isinstance(seq, MyStream)
    # and the resource is the *same object*, not merely an equal one. This
    # assertion used to read `seq.resource == "db-handle"` against a string
    # literal, which pinned that the attribute survived rather than that it was
    # the one the constructor assigned - so it passed while every derivation
    # re-entered __init__ and built a new one.
    assert seq.resource is acquired


@pytest.mark.asyncio
async def test_a_subclass_constructor_runs_once_per_pipeline() -> None:
    # given a subclass that counts its own construction
    runs = []

    class CountingStream(Stream):
        def __init__(self, source, close_handlers=None) -> None:
            super().__init__(source, close_handlers)
            runs.append(1)

    # when a pipeline is built out of it
    CountingStream([1, 2, 3]).map(lambda x: x).filter(lambda x: True).parallel().sorted()

    # then the constructor ran once, at the caller's `CountingStream(...)`, and
    # not once per stage. Before derive-without-reinit this reported five: one
    # explicit, plus one for each of the four derivations, because _derive()
    # built the next stage with type(self)(source, close_handlers).
    assert len(runs) == 1


@pytest.mark.asyncio
async def test_a_resource_acquired_in_the_constructor_is_acquired_once() -> None:
    # given the shape that actually leaks: a subclass releasing its resource in
    # an overridden close() rather than through on_close(). The on_close()
    # shape does not leak, because _close_handlers is shared by reference and
    # every stage's handler lands in the same list - the shared list masks it.
    opened, closed = [], []

    class ConnStream(Stream):
        def __init__(self, source, close_handlers=None) -> None:
            super().__init__(source, close_handlers)
            self.conn = object()
            opened.append(self.conn)

        def close(self) -> None:
            super().close()
            closed.append(self.conn)

    # when
    s = ConnStream([1, 2, 3]).map(lambda x: x).filter(lambda x: True)
    s.close()

    # then one resource was acquired and that one was released. Before the
    # change this was three opened and one closed, leaving two orphans that
    # nothing could reach.
    assert len(opened) == 1
    assert len(closed) == 1
    assert closed[0] is opened[0]


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
async def test_for_each_ordered_follows_the_streams_executor_when_ordered() -> None:
    # given a mapper slow enough that a single-flight drive would show up in
    # wall clock: four elements, each sleeping, under four workers
    seen: list[int] = []

    # when
    started = time.time()
    await Stream.of([1, 2, 3, 4]).parallel().map(_delayed).for_each_ordered(seen.append)
    elapsed = time.time() - started

    # then the consumer saw encounter order, and the chain still raced - the
    # sequential drive would cost the sum of the sleeps (0.08 + 0.06 + 0.04 +
    # 0.02 = 0.2s), the racing one the longest of them (0.08s)
    assert seen == [1, 2, 3, 4]
    assert elapsed < 0.15


@pytest.mark.asyncio
async def test_for_each_ordered_follows_the_streams_executor_when_unordered() -> None:
    # given
    seen: list[int] = []

    # when
    await Stream.of([1, 2, 3, 4]).parallel().unordered().map(_delayed).for_each_ordered(seen.append)

    # then every element exactly once, under the stream's own executor, with no
    # barrier engaged - so no order is promised
    assert sorted(seen) == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_find_first_on_an_ordered_parallel_stream_follows_the_executor() -> None:
    # when
    it = await Stream.of([1, 2, 3, 4]).parallel().map(_delayed).find_first()
    # then: the true first element, not the first to arrive - and obtained
    # under the racing executor, not by dropping to a sequential drive
    assert it == 1


@pytest.mark.asyncio
async def test_find_first_holds_when_the_op_is_declared_before_parallel() -> None:
    # when: the map runs under the racing executor here as it does for every
    # ordinary terminal - find_first() no longer overrides that
    it = await Stream.of([1, 2, 3, 4]).map(_delayed).parallel().find_first()
    # then
    assert it == 1


@pytest.mark.asyncio
async def test_find_first_on_an_unordered_stream_is_not_released_by_it() -> None:
    # when
    it = await Stream.of([1, 2, 3, 4]).parallel().unordered().map(_delayed).find_first()
    # then the true first element, not any element. This assertion used to be
    # `it in [1, 2, 3, 4]` with a comment saying find_first() behaves as
    # find_any() here - which contradicted both the stream-find-first
    # capability and test_terminal_sinks.py, and passed only because it
    # admitted every answer. ALWAYS is the demand that survives unordered()
    assert it == 1


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
    from snakestream.terminals import CountSink

    async def source():
        for i in range(10):
            yield i

    async def other():
        for i in range(10):
            yield i

    # when: the same chain and terminal, driven both ways
    fused = await SEQUENTIAL.value([], source(), CountSink(), False)
    generic = await super(type(SEQUENTIAL), SEQUENTIAL).value([], other(), CountSink(), False)

    # then
    assert fused == generic == 10


@pytest.mark.asyncio
async def test_fork_join_falls_through_to_the_generic_value_for_a_non_partitioning_terminal() -> None:
    # make-combiners-live: _ForkJoin now overrides value() (task 2.1), but
    # only a terminal whose can_partition() is True takes the new path -
    # every other terminal, which is most of them, still drains through the
    # untouched generic form: a batch's chain is built fresh per element, not
    # shared across a single chain such a terminal could be fused onto.
    assert type(SEQUENTIAL).value is not type(SEQUENTIAL).__mro__[1].value
    assert type(FORK_JOIN).value is not type(FORK_JOIN).__mro__[1].value

    from snakestream.sink import TerminalSink

    class _NeverPartitions(TerminalSink):
        def _create_container(self):
            return []

        async def accept(self, element):
            self._container.append(element)

    fused = await Stream.of([1, 2, 3, 4, 5]).parallel().reduce(0, lambda a, b: a + b)
    generic = await Stream.of([1, 2, 3, 4, 5])._evaluate(_NeverPartitions(), OrderDemand.NONE)

    assert fused == 15
    assert generic == [1, 2, 3, 4, 5]


# --- source acceptance does not depend on execution mode --------------------


class _BareAsyncIter:
    """__aiter__ returning self, __anext__, and deliberately no aclose() —
    the shape an `async def` generator function does NOT produce."""

    def __init__(self, n: int) -> None:
        self._it = iter(range(n))

    def __aiter__(self) -> _BareAsyncIter:
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
    # aiter() called once per pull instead of once for the whole run would
    # give the source a fresh iterator on every pull and yield elements
    # more than once, which an existence-only assertion would happily pass.
    # (This particular chain has no intermediate ops, so it degenerates to
    # a single sequential pass rather than exercising fork/join's batching -
    # see test_fork_join.py's own version of this scenario, over a chain
    # with a real op, for the one that does.)
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


# --- a subclass may define any constructor signature -----------------------
#
# Derivation copies rather than constructs, so nothing forces a subclass to
# accept the base class's (source, close_handlers) parameters. That freedom is
# the point of the change as much as the resource churn is: it is what makes
# the resource-wrapping subclass CLAUDE.md documents actually writable.


@pytest.mark.asyncio
async def test_a_subclass_taking_one_unrelated_argument_can_be_extended() -> None:
    # given the natural way to write the documented use case, which used to
    # raise TypeError on its first intermediate op
    class DsnStream(Stream):
        def __init__(self, dsn) -> None:
            self.dsn = dsn
            super().__init__([1, 2, 3])

    # when
    s = DsnStream("db://x").map(lambda x: x * 2).parallel()

    # then
    assert isinstance(s, DsnStream)
    assert s.dsn == "db://x"
    assert await s.collect(to_list()) == [2, 4, 6]


@pytest.mark.asyncio
async def test_a_subclass_taking_no_arguments_at_all_can_be_extended() -> None:
    class NullaryStream(Stream):
        def __init__(self) -> None:
            super().__init__([1, 2, 3])

    s = NullaryStream().filter(lambda x: x > 1).sequential()
    assert isinstance(s, NullaryStream)
    assert await s.collect(to_list()) == [2, 3]


@pytest.mark.asyncio
async def test_subclass_state_is_shared_across_a_pipelines_stages() -> None:
    # given a subclass holding mutable state
    class StatefulStream(Stream):
        def __init__(self, source, close_handlers=None) -> None:
            super().__init__(source, close_handlers)
            self.seen = []

    original = StatefulStream([1, 2, 3])
    derived = original.map(lambda x: x)

    # when the derived stage mutates it
    derived.seen.append("touched")

    # then the original sees it: one resource per pipeline, not one per stage.
    # This is the reading that makes the already-shared _close_handlers list
    # coherent - registered once, released once by a single close().
    assert original.seen == ["touched"]
    assert derived.seen is original.seen


def test_stream_defines_no_copy_hook() -> None:
    # the default shallow copy is correct here, every attribute a Stream holds
    # being one a derived stage should share. Defining __copy__ would mean
    # hand-maintaining that list and would put the wrong class in a subclass
    # author's way.
    assert "__copy__" not in vars(Stream)


@pytest.mark.asyncio
async def test_a_subclasss_copy_hook_governs_derivation() -> None:
    # the consequence of the above, stated rather than left to be discovered:
    # a __copy__ a subclass defines for unrelated reasons now runs on every op
    copies = []

    class HookedStream(Stream):
        def __copy__(self):
            copies.append(1)
            clone = Stream.__new__(HookedStream)
            clone.__dict__.update(self.__dict__)
            return clone

    s = HookedStream([1, 2, 3]).map(lambda x: x)
    assert copies == [1]
    assert isinstance(s, HookedStream)
