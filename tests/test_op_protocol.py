import pytest

from snakestream.collector import to_list
from snakestream.sink import GeneratorBridgeSink, Op, Sink
from snakestream.stream import (
    _DistinctOp,
    _FilterOp,
    _FlatMapOp,
    _LimitOp,
    _MapOp,
    _PeekOp,
    _SkipOp,
    _SortedOp,
    Stream,
)


_SHIPPED_OPS = [
    _FilterOp,
    _MapOp,
    _PeekOp,
    _SortedOp,
    _FlatMapOp,
    _DistinctOp,
    _LimitOp,
    _SkipOp,
]

_STATEFUL_OPS = [_DistinctOp(), _LimitOp(2), _SkipOp(2)]


@pytest.mark.parametrize("op_cls", _SHIPPED_OPS)
def test_every_shipped_op_is_an_op(op_cls) -> None:
    # then
    assert issubclass(op_cls, Op)


def test_a_minimal_op_reports_no_shared_state() -> None:
    # given an op that implements only link()
    class _StatelessOp(Op):
        def link(self, downstream: Sink) -> Sink:
            return downstream

    # then
    assert _StatelessOp().make_shared_state() is None


def test_an_op_without_link_cannot_be_instantiated() -> None:
    # given a subclass that never implements the one abstract member
    class _IncompleteOp(Op):
        pass

    # then
    with pytest.raises(TypeError):
        _IncompleteOp()


@pytest.mark.parametrize("op", _STATEFUL_OPS)
def test_stateful_op_makes_a_fresh_empty_container_each_call(op) -> None:
    # when
    first = op.make_shared_state()
    second = op.make_shared_state()
    # then
    assert first is not None
    assert first is not second
    assert first == second
    assert first in ([0], set())


@pytest.mark.asyncio
async def test_state_map_holds_entries_only_for_stateful_ops() -> None:
    # given a chain mixing stateful and stateless ops
    stream = Stream.of([1, 2, 3]).parallel().map(lambda x: x).distinct().filter(lambda x: True).limit(2)
    chain = stream._chain
    # when the state map is built the way _parallel() builds it
    state_map = {}
    for op in chain:
        state = op.make_shared_state()
        if state is not None:
            state_map[op] = state
    # then
    stateful = [op for op in chain if isinstance(op, (_DistinctOp, _LimitOp, _SkipOp))]
    assert len(stateful) == 2
    assert list(state_map.keys()) == stateful


@pytest.mark.asyncio
async def test_a_stateless_ops_sink_begins_on_an_empty_state_map() -> None:
    # given a sink built from a stateless op onto a terminal
    bridge = GeneratorBridgeSink()
    sink = _MapOp(lambda x: x).link(bridge)
    # when
    await sink.begin({})
    # then begin propagated downstream, creating the bridge's container
    assert bridge.drain() == []


@pytest.mark.asyncio
async def test_shared_state_still_reaches_the_sinks_of_a_parallel_chain() -> None:
    # given a chain whose correctness depends on the state map built above
    it = await Stream.of([1, 1, 2, 2, 3, 3]).parallel().distinct().collect(to_list)
    # then every duplicate was seen by whichever branch pulled it
    assert sorted(it) == [1, 2, 3]
