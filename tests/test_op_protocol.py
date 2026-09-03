import pytest

from snakestream.collectors import to_list
from snakestream.ordering import Ordering, is_ordered
from snakestream.sink import GeneratorBridgeSink, Op, Sink
from snakestream.ops import (
    _DistinctOp,
    _FilterOp,
    _FlatMapOp,
    _LimitOp,
    _MapOp,
    _PeekOp,
    _SkipOp,
    _SortedOp,
    _UnorderedOp,
)
from snakestream.stream import Stream


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
    class _LinkOnlyOp(Op):
        def link(self, downstream: Sink) -> Sink:
            return downstream

    # then
    assert _LinkOnlyOp().make_shared_state() is None


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
    # "empty" is per container type: an empty set for distinct, a zeroed
    # counter for limit/skip
    for container in (first, second):
        assert container == set() if isinstance(container, set) else container.value == 0


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
    assert bridge.buffer == []


@pytest.mark.asyncio
async def test_shared_state_still_reaches_the_sinks_of_a_parallel_chain() -> None:
    # given a chain whose correctness depends on the state map built above
    it = await Stream.of([1, 1, 2, 2, 3, 3]).parallel().distinct().collect(to_list())
    # then every duplicate was seen by whichever branch pulled it
    assert sorted(it) == [1, 2, 3]


_ORDER_SENSITIVE_OPS = [_LimitOp, _SkipOp, _DistinctOp]


def test_a_minimal_op_is_not_order_sensitive() -> None:
    # given an op that implements only link()
    class _LinkOnlyOp(Op):
        def link(self, downstream: Sink) -> Sink:
            return downstream

    # then order-sensitivity is opt-in, like ordering
    assert _LinkOnlyOp.order_sensitive is False


@pytest.mark.parametrize("op_cls", _ORDER_SENSITIVE_OPS)
def test_the_three_position_dependent_ops_declare_order_sensitivity(op_cls) -> None:
    # then limit/skip/distinct select on position, so they say so
    assert op_cls.order_sensitive is True


@pytest.mark.parametrize("op_cls", [c for c in [*_SHIPPED_OPS, _UnorderedOp] if c not in _ORDER_SENSITIVE_OPS])
def test_no_other_shipped_op_declares_order_sensitivity(op_cls) -> None:
    # then - sorted() included: it declares Ordering.SET instead, which is the
    # first clause of the split rule and needs no second flag
    assert op_cls.order_sensitive is False


def test_sorted_declares_ordering_set_rather_than_order_sensitivity() -> None:
    # then the two declarations say different things and sorted() uses the
    # other one: what it does *to* the characteristic, not what it reads from it
    assert _SortedOp.ordering is Ordering.SET
    assert _SortedOp.order_sensitive is False


def test_the_fold_over_a_preserving_chain_returns_its_seed() -> None:
    # given a chain that says nothing about ordering either way
    chain = [_MapOp(lambda x: x), _FilterOp(lambda x: True), _PeekOp(lambda x: None)]

    # then the answer is whatever came in - which is what a chain *suffix*
    # needs, since the ops that decided it sit before the split
    assert is_ordered(chain) is True
    assert is_ordered(chain, initial=False) is False


def test_a_sort_in_the_chain_overrides_an_unordered_seed() -> None:
    # given a suffix that sorts
    chain = [_MapOp(lambda x: x), _SortedOp(lambda a, b: a - b), _LimitOp(2)]

    # then SET wins over the seed, because a sort claims its output is ordered
    assert is_ordered(chain, initial=False) is True

    # and it still wins read only as far as its own position
    assert is_ordered(chain, upto=1, initial=False) is False


def test_unordered_in_the_chain_overrides_an_ordered_seed() -> None:
    # given a suffix that clears
    chain = [_UnorderedOp(), _MapOp(lambda x: x)]

    # then CLEAR wins over the seed too - the seed only survives PRESERVE
    assert is_ordered(chain, initial=True) is False
