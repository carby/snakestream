"""The reorder barrier: what limit/skip/distinct/sorted select under the racing
executor when the pipeline is ordered at their position, what they select when
it is not, and what the bounded read-ahead that makes the first possible costs.

The setup every behavioural test here shares is a source whose *early*
elements are the expensive ones. That is what separates the two paths: under a
plain race the cheap tail overtakes the slow head and an order-sensitive op
decides on arrival order, which is not encounter order. Sleep values are the
same shape as tests/test_unordered.py's - long enough to be decisive on a
loaded machine, short enough that the file stays quick.
"""

import asyncio

import pytest

from snakestream import Stream
from snakestream.collectors import to_list
from snakestream import execution
from snakestream.execution import (
    PROCESSES,
    OrderDemand,
    _Window,
    _guarded,
    _in_flight,
    _release_in_order,
    _split_point,
    group_through,
)
from snakestream.ops import _DistinctOp, _LimitOp, _SkipOp, _SortedOp
from snakestream.sink import IntermediateSink, StatelessOp


def _asc(a: int, b: int) -> int:
    return a - b


async def _agen(n: int):
    for i in range(n):
        yield i


SLOW_HEAD = 5
SOURCE = list(range(12))


async def _slow_head(n: int) -> int:
    """Expensive for the first five elements, cheap for the rest - the
    roadmap's reproduction, and the shape that makes arrival order and
    encounter order disagree."""
    await asyncio.sleep(0.05 if n < SLOW_HEAD else 0.001)
    return n


# --- the split rule ---------------------------------------------------------
#
# Two callers ask for a split. These first tests isolate the *operation*
# clause by passing OrderDemand.NONE, so nothing but an op in the chain can
# produce a split point; the terminal clause has its own tests below.


def _chain(stream: Stream) -> list:
    return stream._chain


def _op_split(chain: list, ordered_in: bool = True):
    """The split an operation asks for, with the terminal clause switched off."""
    return _split_point(chain, OrderDemand.NONE, ordered_in)


def _with_op(stream: Stream, op_cls) -> Stream:
    if op_cls is _LimitOp:
        return stream.limit(3)
    if op_cls is _SkipOp:
        return stream.skip(3)
    return stream.distinct()


@pytest.mark.asyncio
async def test_an_order_preserving_chain_has_no_split_point() -> None:
    # given map/filter/peek, none of which reads position
    chain = _chain(Stream.of(SOURCE).parallel().map(lambda x: x).filter(lambda x: True).peek(lambda x: None))
    # then nothing has to see the whole stream, so the chain races end to end
    assert _op_split(chain) is None


@pytest.mark.asyncio
async def test_an_empty_chain_has_no_split_point() -> None:
    # then
    assert _op_split(_chain(Stream.of(SOURCE).parallel())) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("op_cls", [_LimitOp, _SkipOp, _DistinctOp])
async def test_an_order_sensitive_op_at_an_ordered_position_splits(op_cls) -> None:
    # given the op queued after an order-preserving one
    stream = _with_op(Stream.of(SOURCE).parallel().map(lambda x: x), op_cls)
    # then it is the split point: it selects on position and the pipeline has
    # a position to speak of
    assert _op_split(_chain(stream)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("op_cls", [_LimitOp, _SkipOp, _DistinctOp])
async def test_an_order_sensitive_op_at_an_unordered_position_does_not_split(op_cls) -> None:
    # given the same op, with unordered() queued before it
    stream = _with_op(Stream.of(SOURCE).parallel().unordered(), op_cls)
    # then the caller has said any answer will do, so no barrier is inserted
    assert _op_split(_chain(stream)) is None


@pytest.mark.asyncio
async def test_a_sort_splits_even_at_an_unordered_position() -> None:
    # given the first clause of the split rule, which is the non-obvious one
    chain = _chain(Stream.of(SOURCE).parallel().unordered().sorted(_asc))
    # then: a sort claims its output is ordered, so it must see the whole
    # stream to make that claim true - being at an unordered position is
    # exactly what it is entitled to change
    assert _op_split(chain) == 1
    assert isinstance(chain[1], _SortedOp)


@pytest.mark.asyncio
async def test_the_first_split_point_wins_over_a_later_one() -> None:
    # given a sort at an unordered position followed by a limit
    chain = _chain(Stream.of(SOURCE).parallel().unordered().sorted(_asc).limit(3))
    # then it splits at the sort, not at the limit: splitting at the limit
    # would take the three smallest of a wrongly-merged sort
    assert _op_split(chain) == 1
    assert isinstance(chain[1], _SortedOp)


# --- the split rule, terminal clause ----------------------------------------


@pytest.mark.asyncio
async def test_an_order_observing_terminal_splits_at_the_end_of_the_chain() -> None:
    # given an ordered chain that no operation in it needs order for
    chain = _chain(Stream.of(SOURCE).parallel().map(lambda x: x).filter(lambda x: True))
    # then the split is past the last op: everything races and only delivery is
    # reordered, which is the whole difference between this and a mid-chain
    # barrier
    assert _split_point(chain, OrderDemand.IF_ORDERED, True) == len(chain)


@pytest.mark.asyncio
async def test_an_order_blind_terminal_does_not_split() -> None:
    # given the same chain, asked for by count()/for_each()/any_match()
    chain = _chain(Stream.of(SOURCE).parallel().map(lambda x: x).filter(lambda x: True))
    # then nothing is owed and nothing is paid
    assert _split_point(chain, OrderDemand.NONE, True) is None


@pytest.mark.asyncio
async def test_an_unordered_pipeline_does_not_split_for_its_terminal() -> None:
    # given a pipeline the caller declared unordered
    chain = _chain(Stream.of(SOURCE).parallel().unordered().map(lambda x: x))
    # then the terminal's demand goes unmet by the caller's own declaration
    assert _split_point(chain, OrderDemand.IF_ORDERED, True) is None


@pytest.mark.asyncio
async def test_an_operations_split_wins_over_the_terminals() -> None:
    # given both clauses live at once
    chain = _chain(Stream.of(SOURCE).parallel().map(lambda x: x).limit(3))
    # then the operation's index wins: it is earlier, and everything past it
    # arrives in order anyway
    assert _split_point(chain, OrderDemand.IF_ORDERED, True) == 1


@pytest.mark.asyncio
async def test_the_terminal_clause_reads_the_carried_ordering_seed() -> None:
    # given a chain that says nothing about ordering, as a resumed tail is
    chain = _chain(Stream.of(SOURCE).parallel().map(lambda x: x))
    # then it splits or not on what the ops before the split had decided
    assert _split_point(chain, OrderDemand.IF_ORDERED, True) == len(chain)
    assert _split_point(chain, OrderDemand.IF_ORDERED, False) is None


# --- the four operations, on an ordered pipeline ----------------------------


@pytest.mark.asyncio
async def test_limit_selects_the_first_n_in_encounter_order() -> None:
    # when
    res = await Stream.of(SOURCE).parallel().map(_slow_head).limit(SLOW_HEAD).collect(to_list())
    # then the five slow elements, not the five that finished first
    assert res == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_skip_drops_the_first_n_in_encounter_order() -> None:
    # when
    res = await Stream.of(SOURCE).parallel().map(_slow_head).skip(SLOW_HEAD).collect(to_list())
    # then
    assert res == [5, 6, 7, 8, 9, 10, 11]


@pytest.mark.asyncio
async def test_sorted_sorts_across_branches_over_an_async_source() -> None:
    # given an async source, where every branch really does take a share
    async def descending():
        for i in range(12, 0, -1):
            await asyncio.sleep(0)
            yield i

    # when
    res = await Stream.of(descending()).parallel().sorted(_asc).collect(to_list())
    # then one sort over the whole stream, not one per branch's subset
    assert res == list(range(1, 13))


@pytest.mark.asyncio
async def test_sorted_sorts_across_branches_over_a_sync_source() -> None:
    # given the same pipeline over a list, and a peek recording what the
    # branches' heads actually saw - so a pass here is the ordering
    # requirement being honoured, not one branch happening to take everything
    seen: list[int] = []

    res = await Stream.of(list(range(12, 0, -1))).parallel().peek(seen.append).sorted(_asc).collect(to_list())

    # then
    assert res == list(range(1, 13))
    assert sorted(seen) == list(range(1, 13))


class _Equal:
    """Compares and hashes equal to its peers, but stays distinguishable - so
    which member of an equal group distinct() kept is observable."""

    def __init__(self, key: int, tag: int) -> None:
        self.key = key
        self.tag = tag

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Equal) and self.key == other.key

    def __hash__(self) -> int:
        return hash(self.key)


@pytest.mark.asyncio
async def test_distinct_keeps_the_earliest_encountered_of_each_equal_group() -> None:
    # given two equal groups, each member tagged with its source position
    source = [_Equal(key, tag) for tag, key in enumerate([0, 1, 0, 1, 0, 1, 0, 1])]

    async def slow_head(e: _Equal) -> _Equal:
        await asyncio.sleep(0.05 if e.tag < 4 else 0.001)
        return e

    # when
    res = await Stream.of(source).parallel().map(slow_head).distinct().collect(to_list())

    # then the survivors are the first of each group in encounter order
    assert [e.tag for e in res] == [0, 1]


# --- the same four with unordered() queued first ----------------------------


@pytest.mark.asyncio
async def test_an_unordered_limit_takes_the_first_n_to_arrive() -> None:
    # when
    res = await Stream.of(SOURCE).parallel().unordered().map(_slow_head).limit(SLOW_HEAD).collect(to_list())
    # then still five elements of the source, but selected by arrival: the
    # cheap tail overtakes the slow head
    assert len(res) == SLOW_HEAD
    assert set(res) <= set(SOURCE)
    assert res != [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_an_unordered_skip_drops_the_first_n_to_arrive() -> None:
    # when
    res = await Stream.of(SOURCE).parallel().unordered().map(_slow_head).skip(SLOW_HEAD).collect(to_list())
    # then exactly n dropped, but not the first n in source order
    assert len(res) == len(SOURCE) - SLOW_HEAD
    assert sorted(res) != [5, 6, 7, 8, 9, 10, 11]


@pytest.mark.asyncio
async def test_an_unordered_distinct_keeps_an_arbitrary_representative() -> None:
    # when
    res = await Stream.of([1, 1, 2, 2, 3, 3]).parallel().unordered().distinct().collect(to_list())
    # then the cardinality guarantee holds; which member survived does not
    assert sorted(res) == [1, 2, 3]


@pytest.mark.asyncio
async def test_an_unordered_pipeline_pays_no_head_of_line_delay() -> None:
    # given a pipeline whose first element is far slower than the rest
    async def one_slow_element(n: int) -> int:
        await asyncio.sleep(0.3 if n == 0 else 0.0)
        return n

    loop = asyncio.get_running_loop()

    # when the ordered form is asked for its first element
    ordered = Stream.of(list(range(40))).parallel().map(one_slow_element).distinct().iterator()
    start = loop.time()
    assert await anext(ordered) == 0
    ordered_wait = loop.time() - start
    await ordered.aclose()

    # and the unordered form is asked for its first
    unordered = Stream.of(list(range(40))).parallel().unordered().map(one_slow_element).distinct().iterator()
    start = loop.time()
    first = await anext(unordered)
    unordered_wait = loop.time() - start
    await unordered.aclose()

    # then unordered() is a performance lever, not only a semantic one: it does
    # not hold a finished element back waiting for element 0
    assert first != 0
    assert unordered_wait < 0.1 <= ordered_wait


@pytest.mark.asyncio
async def test_unordered_applies_only_to_ops_queued_after_it() -> None:
    # when the limit is queued before unordered()
    res = await Stream.of(SOURCE).parallel().map(_slow_head).limit(SLOW_HEAD).unordered().collect(to_list())
    # then it is still at an ordered position and still *selects* the first
    # five in encounter order. Delivery is a separate question and the caller
    # answered it: unordered() at the end of the chain means the collector is
    # owed no barrier, so these five may arrive in any order.
    assert sorted(res) == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_a_sort_re_imposes_the_requirement_for_what_follows() -> None:
    # when
    res = await Stream.of(list(range(12, 0, -1))).parallel().unordered().sorted(_asc).limit(3).collect(to_list())
    # then the limit selects on the sorted encounter order, which it could only
    # do because the sort restored the characteristic
    assert res == [1, 2, 3]


# --- the executor governs the whole pipeline --------------------------------


@pytest.mark.asyncio
async def test_an_order_sensitive_op_queued_before_parallel_is_still_honoured() -> None:
    # when .parallel() is declared last, so the whole chain runs under RACING
    res = await Stream.of(SOURCE).map(_slow_head).limit(SLOW_HEAD).parallel().collect(to_list())
    # then
    assert res == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_a_sort_queued_before_parallel_is_still_honoured() -> None:
    # when
    res = await Stream.of(list(range(12, 0, -1))).sorted(_asc).parallel().collect(to_list())
    # then
    assert res == list(range(1, 13))


@pytest.mark.asyncio
async def test_a_barrier_is_not_a_third_mode() -> None:
    # given a pipeline that inserts one
    stream = Stream.of(SOURCE).parallel().sorted(_asc)
    # then it still reports the executor it carries
    assert stream.is_parallel() is True
    assert await stream.collect(to_list()) == SOURCE


# --- bounded read-ahead -----------------------------------------------------


@pytest.mark.asyncio
async def test_a_slow_first_element_does_not_draw_the_whole_source_in() -> None:
    # given a source far longer than the window whose first element's upstream
    # work is far slower than every other element's
    pulled: list[int] = []

    async def counting():
        for i in range(400):
            pulled.append(i)
            yield i

    async def one_slow_element(n: int) -> int:
        await asyncio.sleep(0.2 if n == 0 else 0.0)
        return n

    # when the first element is taken
    agen = Stream.of(counting()).parallel().map(one_slow_element).distinct().iterator()
    first = await anext(agen)
    pulled_before_first_release = len(pulled)
    await agen.aclose()

    # then the read-ahead stayed inside the window rather than growing with
    # the source
    assert first == 0
    assert pulled_before_first_release <= _in_flight(PROCESSES)


@pytest.mark.asyncio
async def test_closing_while_a_branch_is_blocked_on_the_window_does_not_hang() -> None:
    # given an unbounded source and a first element slow enough that every
    # branch parks on the window before it lands
    async def endless():
        i = 0
        while True:
            yield i
            i += 1

    async def one_slow_element(n: int) -> int:
        await asyncio.sleep(5 if n == 0 else 0.0)
        return n

    before = len(asyncio.all_tasks())
    agen = Stream.of(endless()).parallel().map(one_slow_element).distinct().iterator()
    pull = asyncio.create_task(anext(agen))
    await asyncio.sleep(0.05)
    pull.cancel()
    await asyncio.gather(pull, return_exceptions=True)

    # when / then aclose() returns rather than waiting on the blocked branch
    await asyncio.wait_for(agen.aclose(), timeout=2)
    await asyncio.sleep(0)
    assert len(asyncio.all_tasks()) == before


@pytest.mark.asyncio
async def test_a_wider_race_is_given_a_wider_window() -> None:
    # given a race across more branches than the default worker count, over a
    # source whose head element is far slower than the rest, so the branches
    # fill the window behind it. No public path reaches a non-default worker
    # count - PROCESSES is bound into RACING at import - so the executor is
    # swapped directly, the way the primitives are driven elsewhere in this file
    pulled: list[int] = []

    async def counting():
        for i in range(400):
            pulled.append(i)
            yield i

    async def one_slow_element(n: int) -> int:
        await asyncio.sleep(0.3 if n == 0 else 0.0)
        return n

    wide = 2 * PROCESSES

    # when the first element is taken
    stream = Stream.of(counting()).parallel().map(one_slow_element)
    stream._executor = execution.Racing(wide)
    agen = stream.iterator()
    first = await anext(agen)
    pulled_before_first_release = len(pulled)
    await agen.aclose()

    # then the wider race got the wider window rather than the same one divided
    # further. Asserted against the derivation at both counts, never a measured
    # figure: the point is which bound applies, not where the branches landed
    assert first == 0
    assert pulled_before_first_release <= _in_flight(wide)
    assert pulled_before_first_release > _in_flight(PROCESSES)


@pytest.mark.asyncio
async def test_over_pull_upstream_of_an_ordered_limit_is_bounded() -> None:
    # given far more source than the limit needs
    seen: list[int] = []

    # when
    res = await Stream.of(list(range(400))).parallel().peek(seen.append).limit(3).collect(to_list())

    # then the selection is exact and the over-pull is not unbounded
    assert res == [0, 1, 2]
    assert 3 <= len(seen) <= _in_flight(PROCESSES)


# --- cancellation across the barrier ----------------------------------------


@pytest.mark.asyncio
async def test_an_ordered_limit_over_an_unbounded_source_terminates() -> None:
    # given an infinite source, so only cancellation reaching the shared pull
    # can end this
    closed: list[bool] = []

    async def endless():
        try:
            i = 0
            while True:
                yield i
                i += 1
        finally:
            closed.append(True)

    # when
    res = await asyncio.wait_for(
        Stream.of(endless()).parallel().map(lambda x: x).limit(5).collect(to_list()),
        timeout=5,
    )

    # then
    assert res == [0, 1, 2, 3, 4]
    assert closed == [True]


class _CountingSource:
    """A shared source that records how often it is closed, so 'exactly once'
    is observable with a barrier in play."""

    def __init__(self, n: int) -> None:
        self._it = iter(range(n))
        self.closes = 0

    def __aiter__(self) -> "_CountingSource":
        return self

    async def __anext__(self) -> int:
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration from None

    async def aclose(self) -> None:
        self.closes += 1


@pytest.mark.asyncio
async def test_a_barrier_does_not_change_how_the_shared_source_is_closed() -> None:
    # given the same cancelling pipeline with and without a barrier
    ordered = _CountingSource(200)
    unordered = _CountingSource(200)

    # when
    res = await Stream.of(ordered).parallel().limit(4).collect(to_list())
    await Stream.of(unordered).parallel().unordered().limit(4).collect(to_list())

    # then the selection is the ordered one, and closing is untouched: every
    # branch's _guarded() closes the shared source on its way out, which is
    # what the racing executor has always done and what the barrier leaves
    # alone. An async generator - the shape source normalization builds - runs
    # its finally once regardless; see the generator form below.
    assert res == [0, 1, 2, 3]
    assert ordered.closes == unordered.closes


@pytest.mark.asyncio
async def test_a_generator_source_behind_a_barrier_runs_its_finally_once() -> None:
    # given the source shape _normalize() builds
    closed: list[bool] = []

    async def source():
        try:
            for i in range(200):
                yield i
        finally:
            closed.append(True)

    # when
    res = await Stream.of(source()).parallel().limit(4).collect(to_list())

    # then
    assert res == [0, 1, 2, 3]
    assert closed == [True]


class _NoCloseSource:
    """__aiter__/__anext__ and nothing else - the source shape that has no
    aclose() to call."""

    def __init__(self, n: int) -> None:
        self._it = iter(range(n))

    def __aiter__(self) -> "_NoCloseSource":
        return self

    async def __anext__(self) -> int:
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration from None


@pytest.mark.asyncio
async def test_a_source_with_no_aclose_still_races_behind_a_barrier() -> None:
    # when
    res = await Stream.of(_NoCloseSource(10)).parallel().sorted(_asc).collect(to_list())
    # then no AttributeError from the close path
    assert res == list(range(10))


# --- ordering changes the order, and nothing else ---------------------------


@pytest.mark.asyncio
async def test_every_element_appears_exactly_once_behind_a_barrier() -> None:
    # given repeated but distinguishable elements
    source = [_Equal(i % 4, i) for i in range(24)]
    # when: skip() admits everything past the first four
    res = await Stream.of(source).parallel().skip(4).collect(to_list())
    # then nothing lost, nothing duplicated
    assert [e.tag for e in res] == list(range(4, 24))


@pytest.mark.asyncio
async def test_a_flat_map_upstream_of_a_barrier_keeps_every_output() -> None:
    # given a head op that turns one source element into several - the case a
    # per-element tag has no answer for
    res = await Stream.of([1, 2, 3]).parallel().flat_map(lambda x: Stream.of([x, x * 10])).limit(6).collect(to_list())
    # then every output of group 0, then group 1, then group 2
    assert res == [1, 10, 2, 20, 3, 30]


@pytest.mark.asyncio
async def test_a_filter_upstream_of_a_barrier_does_not_stall_the_merge() -> None:
    # given a head op that drops elements, leaving groups with no output at all
    res = await Stream.of(list(range(20))).parallel().filter(lambda x: x % 5 == 0).limit(3).collect(to_list())
    # then the empty groups advanced the merge rather than holding it
    assert res == [0, 5, 10]


@pytest.mark.asyncio
async def test_an_error_upstream_of_a_barrier_propagates_rather_than_hanging() -> None:
    # given a mapper that raises on one element
    def boom(n: int) -> int:
        if n == 3:
            raise ValueError("boom")
        return n

    # when / then it comes out of the terminal rather than deadlocking the
    # merge on the group that never arrives
    with pytest.raises(ValueError, match="boom"):
        await asyncio.wait_for(
            Stream.of(list(range(20))).parallel().map(boom).limit(10).collect(to_list()),
            timeout=5,
        )


# --- the merge's less-travelled paths ---------------------------------------


class _EmitOnEndSink(IntermediateSink):
    """Buffers everything and flushes at end() - the shape _SortedSink has, and
    the one that produces a group with no source position."""

    def __init__(self, downstream) -> None:
        super().__init__(downstream)
        self._buffer: list = []

    async def accept(self, element) -> None:
        self._buffer.append(element)

    async def end(self) -> None:
        for item in self._buffer:
            await self.downstream.accept(item)
        await super().end()


class _EmitOnEndOp(StatelessOp):
    _sink_cls = _EmitOnEndSink


@pytest.mark.asyncio
async def test_a_head_op_that_emits_at_end_is_ordered_after_every_real_group() -> None:
    # given a head chain whose output arrives at end(), with no source index to
    # sort by. No shipped op does this upstream of a barrier - sorted() is
    # always a split point and so is never in the head - so this drives the two
    # primitives directly, the way tests/test_sink.py drives a sink
    lock = asyncio.Lock()
    window = _Window(_in_flight(PROCESSES))
    source = _guarded(aiter(_agen(6)), lock, window)
    branches = [group_through([_EmitOnEndOp()], source, {})]

    # when
    res = [out async for out in _release_in_order(branches, window)]

    # then nothing was lost, and it came out after every real group would have
    assert res == list(range(6))


@pytest.mark.asyncio
async def test_a_cancelling_head_op_stops_its_branch_without_stalling_the_merge() -> None:
    # given a limit at an unordered position - so it stays in the raced head
    # and cancels there - with a sort behind it forcing a barrier
    res = await Stream.of(list(range(40))).parallel().unordered().limit(6).sorted(_asc).collect(to_list())

    # then the head's cancellation ended each branch cleanly and the sort still
    # saw every element the limit admitted
    assert len(res) == 6
    assert res == sorted(res)


@pytest.mark.asyncio
async def test_branches_contending_for_the_last_window_slot_still_pull_in_order(monkeypatch) -> None:
    # given a window of one, so the slot a branch waited for is routinely gone
    # again by the time it holds the lock - and a source that really suspends
    # mid-pull, which is what lets another branch get in between one branch's
    # "not full" check and its assignment. Patching the derivation rather than
    # a constant: it is the single site the size comes from, and no worker
    # count yields a window of one through it
    monkeypatch.setattr(execution, "_in_flight", lambda workers: 1)

    async def slow_source():
        for i in range(60):
            await asyncio.sleep(0)
            yield i

    # when
    res = await Stream.of(slow_source()).parallel().map(lambda x: x).distinct().collect(to_list())

    # then the contention resolved into encounter order rather than a lost or
    # duplicated element
    assert res == list(range(60))


@pytest.mark.asyncio
async def test_a_head_cancelled_before_its_first_pull_yields_nothing() -> None:
    # given limit(0) at an unordered position, so the head reports cancellation
    # from begin() and the branch must not pull even once
    seen: list[int] = []

    res = await Stream.of(list(range(20))).parallel().unordered().peek(seen.append).limit(0).sorted(_asc).collect(to_list())

    # then
    assert res == []
    assert seen == []


# --- a racing sort is stable, ordered or not ---------------------------------
#
# _SortedOp declares Ordering.SET and _split_point()'s first clause fires on it
# unconditionally, so a sort sees the whole stream in encounter order wherever
# it sits - including on a pipeline declared unordered(), where a sort left in
# the raced head would sort each branch's subset instead. That makes the sort's
# tie order encounter order, which is what stability means here.

_TIED = [("a", 5), ("b", 3), ("c", 5), ("d", 1), ("e", 3), ("f", 5)]
_SORTED_BY_SECOND = [("d", 1), ("b", 3), ("e", 3), ("a", 5), ("c", 5), ("f", 5)]


def _by_second(x, y):
    return x[1] - y[1]


async def _jittered(pair):
    """Later elements are cheaper, so the branches finish out of encounter
    order and an unstable sort would show it."""
    await asyncio.sleep(0.02 if pair[0] in ("a", "b") else 0.001)
    return pair


@pytest.mark.asyncio
@pytest.mark.parametrize("run", range(3))
async def test_a_racing_sort_is_stable(run) -> None:
    # when
    it = await Stream.of(_TIED).parallel().map(_jittered).sorted(_by_second).collect(to_list())
    # then
    assert it == _SORTED_BY_SECOND


@pytest.mark.asyncio
@pytest.mark.parametrize("run", range(3))
async def test_a_sort_on_an_unordered_pipeline_is_stable(run) -> None:
    # when
    it = await Stream.of(_TIED).parallel().unordered().map(_jittered).sorted(_by_second).collect(to_list())
    # then: the sort still saw the whole stream, in encounter order
    assert it == _SORTED_BY_SECOND


@pytest.mark.asyncio
async def test_an_unordered_sort_sorts_the_whole_stream_not_per_branch_subsets() -> None:
    # given: a source large enough that per-branch subsets would interleave
    source = [(chr(97 + i), (7 * i) % 13) for i in range(24)]

    # when
    it = await Stream.of(source).parallel().unordered().sorted(lambda x, y: x[1] - y[1]).collect(to_list())

    # then
    assert [pair[1] for pair in it] == sorted(pair[1] for pair in source)
